/**
 * SuperAgent Voice Orchestrator
 * OpenAI Realtime API Integration for Voice-Controlled Multi-Agent Testing
 *
 * Handles:
 * - WebSocket connection to OpenAI Realtime API
 * - Audio streaming (input/output)
 * - Voice transcription to text commands
 * - Command routing to Kaya agent
 * - Response synthesis back to voice
 */

import WebSocket from 'ws';
import { spawn } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs';

// ============================================================================
// Types & Interfaces
// ============================================================================

export interface VoiceIntent {
  type: 'create_test' | 'run_test' | 'fix_failure' | 'validate' | 'status' | 'unknown';
  slots: Record<string, string>;
  raw_command: string;
  confidence?: number;
  needs_clarification?: boolean;
  clarification_prompt?: string;
}

interface KayaResult {
  success: boolean;
  data?: Record<string, any>;
  error?: string;
  execution_time_ms?: number;
  cost_usd?: number;
}

interface RealtimeConfig {
  apiKey: string;
  model?: string;
  voice?: 'alloy' | 'echo' | 'shimmer';
  temperature?: number;
  max_response_tokens?: number;
  redisHost?: string;
  redisPort?: number;
  redisPassword?: string;
}

interface AudioConfig {
  sampleRate: number;
  channels: number;
  encoding: 'pcm16' | 'g711_ulaw' | 'g711_alaw';
}

interface SessionConfig {
  modalities: string[];
  instructions: string;
  voice: string;
  input_audio_format: string;
  output_audio_format: string;
  input_audio_transcription?: {
    model: string;
  };
  turn_detection?: {
    type: string;
    threshold: number;
    prefix_padding_ms: number;
    silence_duration_ms: number;
  };
}

// ============================================================================
// Main Orchestrator Class
// ============================================================================

export class VoiceOrchestrator extends EventEmitter {
  private ws: WebSocket | null = null;
  private isConnected: boolean = false;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;
  private reconnectDelay: number = 2000;
  private sessionId: string | null = null;

  private config: RealtimeConfig;
  private audioConfig: AudioConfig;

  // Audio buffers
  private outputAudioBuffer: Buffer[] = [];

  // State tracking
  private conversationHistory: Array<{ role: string; content: string }> = [];

  // Redis client for transcript storage
  private redisEnabled: boolean = false;

  // Progress tracking for long operations
  private activeOperation: {
    startTime: number;
    operation: string;
    expectedDuration: number;
    statusUpdateInterval?: NodeJS.Timeout;
  } | null = null;

  constructor(config: RealtimeConfig) {
    super();

    this.config = {
      model: 'gpt-4o-realtime-preview-2024-10-01',
      voice: 'alloy',
      temperature: 0.8,
      max_response_tokens: 4096,
      ...config
    };

    this.audioConfig = {
      sampleRate: 24000,
      channels: 1,
      encoding: 'pcm16'
    };

    // Initialize Redis client if config provided
    this.initializeRedis();
  }

  /**
   * Initialize Redis client for transcript storage
   */
  private async initializeRedis(): Promise<void> {
    try {
      // Only initialize if Python Redis client is available
      const redisClientPath = path.join(__dirname, '../../state/redis_client.py');

      if (fs.existsSync(redisClientPath)) {
        this.redisEnabled = true;
        console.log('[Voice] Redis transcript storage enabled');
      } else {
        console.log('[Voice] Redis client not found - transcript storage disabled');
      }
    } catch (error: any) {
      console.warn('[Voice] Failed to initialize Redis:', error.message);
      this.redisEnabled = false;
    }
  }

  // ==========================================================================
  // Connection Management
  // ==========================================================================

  /**
   * Connect to OpenAI Realtime API
   */
  async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const url = 'wss://api.openai.com/v1/realtime?model=' + this.config.model;

        this.ws = new WebSocket(url, {
          headers: {
            'Authorization': `Bearer ${this.config.apiKey}`,
            'OpenAI-Beta': 'realtime=v1'
          }
        });

        this.ws.on('open', () => {
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.emit('connected');
          console.log('[Voice] Connected to OpenAI Realtime API');

          // Configure session
          this.configureSession();
          resolve();
        });

        this.ws.on('message', (data: WebSocket.Data) => {
          this.handleMessage(data);
        });

        this.ws.on('error', (error: Error) => {
          this.emit('error', error);
          console.error('[Voice] WebSocket error:', error.message);
          reject(error);
        });

        this.ws.on('close', () => {
          this.isConnected = false;
          this.emit('disconnected');
          console.log('[Voice] Disconnected from OpenAI Realtime API');

          // Attempt reconnection
          this.attemptReconnect();
        });

      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from OpenAI Realtime API
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
    this.sessionId = null;
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[Voice] Max reconnection attempts reached');
      this.emit('max_reconnect_failed');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`[Voice] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    setTimeout(() => {
      this.connect().catch(err => {
        console.error('[Voice] Reconnection failed:', err.message);
      });
    }, delay);
  }

  // ==========================================================================
  // Session Configuration
  // ==========================================================================

  /**
   * Configure the Realtime API session with voice settings
   */
  private configureSession(): void {
    const sessionConfig: SessionConfig = {
      modalities: ['text', 'audio'],
      instructions: this.getSystemInstructions(),
      voice: this.config.voice || 'alloy',
      input_audio_format: 'pcm16',
      output_audio_format: 'pcm16',
      input_audio_transcription: {
        model: 'whisper-1'
      },
      turn_detection: {
        type: 'server_vad',
        threshold: 0.5,
        prefix_padding_ms: 300,
        silence_duration_ms: 500
      }
    };

    this.sendEvent({
      type: 'session.update',
      session: sessionConfig
    });
  }

  /**
   * Get system instructions for Kaya voice interface
   */
  private getSystemInstructions(): string {
    return `You are Kaya, the orchestrator for SuperAgent - a voice-controlled multi-agent testing system.

Your role is to:
1. Listen to user voice commands about test automation
2. Parse their intent and extract key information
3. Route commands to the appropriate agent (Scribe, Runner, Medic, Gemini, Critic)
4. Provide clear, concise spoken responses

Supported voice intents:
- "create_test": User wants to write a test (e.g., "write a test for user login")
- "run_test": User wants to execute a test (e.g., "run tests/cart.spec.ts")
- "fix_failure": User wants to fix a failed test (e.g., "fix task t_123")
- "validate": User wants to validate a test (e.g., "validate checkout flow")
- "status": User wants task status (e.g., "what's the status of t_456")

Response style:
- Be concise and professional
- Confirm what action you're taking
- Report results clearly
- If there's an error, explain it simply
- Keep responses under 3 sentences when possible

Example responses:
- "I'll write a test for user login using the Scribe agent. This should take about 2 minutes."
- "Running the cart test now. I'll let you know the results."
- "The test passed with 5 assertions verified. Execution took 3.2 seconds."
- "I found 2 issues in that test. The selector is using an index which could be flaky."`;
  }

  // ==========================================================================
  // Message Handling
  // ==========================================================================

  /**
   * Handle incoming messages from Realtime API
   */
  private handleMessage(data: WebSocket.Data): void {
    try {
      const message = JSON.parse(data.toString());

      // Emit raw message for debugging
      this.emit('message', message);

      switch (message.type) {
        case 'session.created':
          this.handleSessionCreated(message);
          break;

        case 'session.updated':
          this.handleSessionUpdated(message);
          break;

        case 'conversation.item.created':
          this.handleConversationItemCreated(message);
          break;

        case 'conversation.item.input_audio_transcription.completed':
          this.handleTranscriptionCompleted(message);
          break;

        case 'response.audio.delta':
          this.handleAudioDelta(message);
          break;

        case 'response.audio.done':
          this.handleAudioDone(message);
          break;

        case 'response.text.delta':
          this.handleTextDelta(message);
          break;

        case 'response.text.done':
          this.handleTextDone(message);
          break;

        case 'response.done':
          this.handleResponseDone(message);
          break;

        case 'error':
          this.handleError(message);
          break;

        default:
          // Log unknown message types for debugging
          console.log('[Voice] Unknown message type:', message.type);
      }
    } catch (error) {
      console.error('[Voice] Error parsing message:', error);
      this.emit('parse_error', error);
    }
  }

  private handleSessionCreated(message: any): void {
    this.sessionId = message.session?.id;
    console.log('[Voice] Session created:', this.sessionId);
    this.emit('session_created', message.session);
  }

  private handleSessionUpdated(message: any): void {
    console.log('[Voice] Session updated');
    this.emit('session_updated', message.session);
  }

  private handleConversationItemCreated(message: any): void {
    this.emit('conversation_item', message.item);
  }

  private handleTranscriptionCompleted(message: any): void {
    const transcript = message.transcript;
    console.log('[Voice] Transcription:', transcript);

    this.emit('transcription', transcript);

    // Store transcript in Redis
    this.storeTranscript(transcript);

    // Parse intent and route to Kaya
    this.processVoiceCommand(transcript);
  }

  /**
   * Store transcript in Redis with 1h TTL
   */
  private async storeTranscript(transcript: string): Promise<void> {
    if (!this.redisEnabled || !this.sessionId) {
      return;
    }

    try {
      const timestamp = new Date().toISOString();
      const transcriptData = {
        text: transcript,
        timestamp,
        session_id: this.sessionId
      };

      // Call Python Redis CLI to store transcript
      const redisCli = path.join(__dirname, 'redis_cli.py');
      const process = spawn('python3', [
        redisCli,
        'add_transcript',
        this.sessionId,
        JSON.stringify(transcriptData)
      ]);

      process.on('close', (code: number | null) => {
        if (code !== 0) {
          console.warn('[Voice] Failed to store transcript in Redis');
        }
      });
    } catch (error: any) {
      console.warn('[Voice] Error storing transcript:', error.message);
    }
  }

  private handleAudioDelta(message: any): void {
    if (message.delta) {
      const audioData = Buffer.from(message.delta, 'base64');
      this.outputAudioBuffer.push(audioData);
      this.emit('audio_delta', audioData);
    }
  }

  private handleAudioDone(_message: any): void {
    const fullAudio = Buffer.concat(this.outputAudioBuffer);
    this.outputAudioBuffer = [];
    this.emit('audio_complete', fullAudio);
  }

  private handleTextDelta(message: any): void {
    if (message.delta) {
      this.emit('text_delta', message.delta);
    }
  }

  private handleTextDone(message: any): void {
    this.emit('text_complete', message.text);
  }

  private handleResponseDone(message: any): void {
    this.emit('response_complete', message.response);
  }

  private handleError(message: any): void {
    console.error('[Voice] API Error:', message.error);
    this.emit('api_error', message.error);
  }

  // ==========================================================================
  // Voice Command Processing
  // ==========================================================================

  /**
   * Process voice command and route to Kaya agent
   */
  private async processVoiceCommand(transcript: string): Promise<void> {
    try {
      // Add to conversation history
      this.conversationHistory.push({
        role: 'user',
        content: transcript
      });

      // Parse intent from transcript
      const intent = this.parseVoiceIntent(transcript);
      this.emit('intent_parsed', intent);

      // Check if clarification is needed
      if (intent.needs_clarification) {
        console.log('[Voice] Command needs clarification');
        await this.speakResponse(intent.clarification_prompt!);
        return;
      }

      // Start progress tracking for long operations
      const expectedDuration = this.estimateOperationDuration(intent.type);
      this.startProgressTracking(intent.type, expectedDuration);

      // Route to Kaya agent via CLI with structured intent
      const result = await this.executeKayaCommand(transcript, intent);

      // Stop progress tracking
      this.stopProgressTracking();

      // Emit result
      this.emit('kaya_result', result);

      // Generate response
      const response = this.generateResponse(result);

      // Send response back to user via voice
      await this.speakResponse(response);

    } catch (error: any) {
      console.error('[Voice] Error processing command:', error);
      this.stopProgressTracking();
      const errorMessage = `I encountered an error processing that command: ${error.message}`;
      await this.speakResponse(errorMessage);
    }
  }

  /**
   * Estimate operation duration based on intent type
   */
  private estimateOperationDuration(intentType: string): number {
    const durations: Record<string, number> = {
      'create_test': 120000,    // 2 minutes for test creation
      'run_test': 30000,        // 30 seconds for test execution
      'fix_failure': 180000,    // 3 minutes for bug fixing
      'validate': 45000,        // 45 seconds for validation
      'status': 2000,           // 2 seconds for status check
      'unknown': 10000          // 10 seconds default
    };

    return durations[intentType] || durations['unknown'];
  }

  /**
   * Start progress tracking for long-running operations
   */
  private startProgressTracking(operation: string, expectedDuration: number): void {
    // Only track operations expected to take >10 seconds
    if (expectedDuration <= 10000) {
      return;
    }

    this.activeOperation = {
      startTime: Date.now(),
      operation,
      expectedDuration
    };

    // Send initial progress update
    const initialUpdate = this.getProgressUpdate(operation, 0, expectedDuration);
    this.speakResponse(initialUpdate);

    // Set up periodic status updates every 15 seconds
    this.activeOperation.statusUpdateInterval = setInterval(() => {
      if (!this.activeOperation) return;

      const elapsed = Date.now() - this.activeOperation.startTime;
      const progressUpdate = this.getProgressUpdate(
        this.activeOperation.operation,
        elapsed,
        this.activeOperation.expectedDuration
      );

      this.emit('progress_update', {
        operation: this.activeOperation.operation,
        elapsed,
        expected: this.activeOperation.expectedDuration,
        message: progressUpdate
      });

      // Only speak every 30 seconds to avoid being too chatty
      if (elapsed % 30000 < 15000) {
        this.speakResponse(progressUpdate);
      }
    }, 15000);
  }

  /**
   * Stop progress tracking
   */
  private stopProgressTracking(): void {
    if (this.activeOperation?.statusUpdateInterval) {
      clearInterval(this.activeOperation.statusUpdateInterval);
    }
    this.activeOperation = null;
  }

  /**
   * Get progress update message
   */
  private getProgressUpdate(operation: string, elapsed: number, expectedDuration: number): string {
    const remainingSeconds = Math.max(0, Math.floor((expectedDuration - elapsed) / 1000));

    const operationNames: Record<string, string> = {
      'create_test': 'creating your test',
      'run_test': 'running the test',
      'fix_failure': 'fixing the bug',
      'validate': 'validating the test in a browser'
    };

    const operationName = operationNames[operation] || 'processing your request';

    if (elapsed < 10000) {
      return `I'm ${operationName}. This should take about ${Math.floor(expectedDuration / 1000)} seconds.`;
    } else if (remainingSeconds > 10) {
      return `Still ${operationName}. About ${remainingSeconds} seconds remaining.`;
    } else {
      return `Almost done ${operationName}. Just a few more seconds.`;
    }
  }

  /**
   * Parse voice command into structured intent with slots
   */
  private parseVoiceIntent(transcript: string): VoiceIntent {
    const normalized = transcript.toLowerCase().trim();
    const intent: VoiceIntent = {
      type: 'unknown',
      slots: {},
      raw_command: transcript,
      confidence: 0
    };

    // Intent patterns with slot extraction
    const patterns = [
      {
        type: 'create_test' as const,
        patterns: [
          /(?:write|create|generate|make)\s+(?:a\s+)?test\s+for\s+(.+)/i,
          /(?:write|create|generate|make)\s+(?:a\s+)?test\s+(?:about|on)\s+(.+)/i,
          /test\s+(?:the\s+)?(.+?)(?:\s+feature)?$/i
        ],
        slotName: 'feature'
      },
      {
        type: 'run_test' as const,
        patterns: [
          /(?:run|execute|start)\s+(?:the\s+)?test[s]?\s+(.+\.spec\.ts)/i,
          /(?:run|execute|start)\s+(.+\.spec\.ts)/i,
          /(?:run|execute|start)\s+(?:all\s+)?(.+?)\s+tests?/i,
          /(?:run|execute|start)\s+(?:the\s+)?test\s+for\s+(.+)/i
        ],
        slotName: 'test_path'
      },
      {
        type: 'fix_failure' as const,
        patterns: [
          /(?:fix|repair|patch)\s+(?:task\s+)?(t_[a-z0-9_]+)/i,
          /(?:fix|repair|patch)\s+(?:the\s+)?(?:failed\s+)?(.+?)\s+test/i,
          /(?:fix|repair|patch)\s+(?:the\s+)?failure\s+(?:in|for)\s+(.+)/i
        ],
        slotName: 'task_id'
      },
      {
        type: 'validate' as const,
        patterns: [
          /(?:validate|verify|check)\s+(?:the\s+)?(.+?)(?:\s+[-–]\s+critical)?$/i,
          /(?:validate|verify|check)\s+(.+?)\s+(?:with\s+)?gemini/i,
          /(?:validate|verify|check)\s+(?:the\s+)?test\s+for\s+(.+)/i
        ],
        slotName: 'test_path'
      },
      {
        type: 'status' as const,
        patterns: [
          /(?:what'?s|what is|show|get)\s+(?:the\s+)?status\s+(?:of\s+)?(?:task\s+)?(t_[a-z0-9_]+)/i,
          /status\s+(?:of\s+)?(?:task\s+)?(t_[a-z0-9_]+)/i,
          /(?:what'?s|what is)\s+happening\s+(?:with\s+)?(?:task\s+)?(t_[a-z0-9_]+)/i
        ],
        slotName: 'task_id'
      }
    ];

    // Try to match each pattern
    for (const { type, patterns: regexes, slotName } of patterns) {
      for (const regex of regexes) {
        const match = normalized.match(regex);
        if (match) {
          intent.type = type;
          intent.slots[slotName] = match[1]?.trim() || '';
          intent.confidence = 0.9;

          // Extract additional slots based on intent type
          if (type === 'validate' && /critical|important|high.?priority/i.test(normalized)) {
            intent.slots.high_priority = 'true';
          }

          if (type === 'create_test' && /scope|scenario/i.test(normalized)) {
            const scopeMatch = normalized.match(/scope[:\s]+(.+)/i);
            if (scopeMatch) {
              intent.slots.scope = scopeMatch[1].trim();
            }
          }

          return intent;
        }
      }
    }

    // Check if command is ambiguous
    const hasTestKeyword = /test/i.test(normalized);
    const hasRunKeyword = /run|execute/i.test(normalized);
    const hasFixKeyword = /fix|repair|patch/i.test(normalized);

    if ((hasTestKeyword || hasRunKeyword || hasFixKeyword) && intent.type === 'unknown') {
      intent.needs_clarification = true;
      intent.clarification_prompt = this.generateClarificationPrompt(normalized);
    }

    return intent;
  }

  /**
   * Generate clarification prompt for ambiguous commands
   */
  private generateClarificationPrompt(command: string): string {
    if (/test/i.test(command) && !/run|execute|write|create/i.test(command)) {
      return "I understand you mentioned a test, but I'm not sure what you want to do. Would you like me to create a test, run a test, or validate a test?";
    }

    if (/fix|repair/i.test(command) && !/task|t_/i.test(command)) {
      return "I can help fix a failed test. Could you provide the task ID? It should look like 't_123'.";
    }

    if (/status/i.test(command) && !/task|t_/i.test(command)) {
      return "I can check the status of a task. Could you provide the task ID? It should look like 't_123'.";
    }

    return "I'm not sure what you want me to do. Could you try rephrasing that? For example, you can say 'write a test for login', 'run tests/cart.spec.ts', or 'what's the status of task t_123'.";
  }

  /**
   * Execute Kaya command via Python CLI with structured intent
   */
  private async executeKayaCommand(command: string, intent?: VoiceIntent): Promise<KayaResult> {
    return new Promise((resolve, reject) => {
      const kayaPath = '/Users/rutledge/Documents/DevFolder/SuperAgent/agent_system/cli.py';

      // Build command args with intent data
      const args = ['kaya', command];
      if (intent) {
        args.push('--intent-type', intent.type);
        args.push('--intent-slots', JSON.stringify(intent.slots));
      }

      // Spawn Kaya process
      const process = spawn('python3', [kayaPath, ...args]);

      let stdout = '';
      let stderr = '';

      process.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      process.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Kaya process exited with code ${code}: ${stderr}`));
          return;
        }

        try {
          // Parse Kaya output
          const result = this.parseKayaOutput(stdout, intent);
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });

      // Timeout after 30 seconds
      setTimeout(() => {
        process.kill();
        reject(new Error('Kaya command timeout'));
      }, 30000);
    });
  }

  /**
   * Parse Kaya CLI output into structured result
   */
  private parseKayaOutput(output: string, intent?: VoiceIntent): KayaResult {
    // Try to parse as JSON first (structured output)
    try {
      const jsonMatch = output.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return {
          success: parsed.success || false,
          data: parsed.data || {},
          error: parsed.error,
          execution_time_ms: parsed.execution_time_ms,
          cost_usd: parsed.cost_usd
        };
      }
    } catch (e) {
      // Fall back to simple parsing
    }

    // Simple parsing - fallback
    const successMatch = output.match(/Success: (true|false)/i);
    const success = successMatch ? successMatch[1].toLowerCase() === 'true' : false;

    return {
      success,
      data: {
        raw_output: output,
        intent: intent?.type
      }
    };
  }

  /**
   * Generate spoken response from Kaya result with natural language
   */
  private generateResponse(result: KayaResult): string {
    if (!result.success) {
      const errorMsg = result.error || 'Unknown error';
      return `I encountered an issue: ${this.simplifyErrorMessage(errorMsg)}. Would you like me to try a different approach?`;
    }

    const action = result.data?.action || 'unknown';
    const data = result.data || {};

    switch (action) {
      case 'test_created':
        return this.generateTestCreatedResponse(data);

      case 'test_executed':
        return this.generateTestExecutedResponse(data);

      case 'bug_fixed':
        return this.generateBugFixedResponse(data);

      case 'test_validated':
        return this.generateTestValidatedResponse(data);

      case 'status_report':
        return this.generateStatusResponse(data);

      case 'full_pipeline':
        return this.generatePipelineResponse(data);

      // Legacy action names for backward compatibility
      case 'route_to_scribe':
        return `I'm creating a test for ${data.feature}. This will use the Scribe agent and should take about 2 minutes.`;

      case 'route_to_runner':
        return `Running test ${data.test_path} now. I'll report back with the results.`;

      case 'route_to_medic':
        return `I'm sending task ${data.task_id} to the Medic agent for repair. This may take a few minutes.`;

      case 'route_to_gemini':
        return `Validating ${data.test_path} with Gemini. This will run the test in a real browser to verify correctness.`;

      case 'get_status':
        return `Let me check the status of task ${data.task_id}.`;

      default:
        return 'Command received and processed successfully.';
    }
  }

  /**
   * Generate natural response for test creation
   */
  private generateTestCreatedResponse(data: any): string {
    const feature = data.feature || 'the feature';
    const testPath = data.test_path;
    const complexity = data.complexity || 'medium';

    if (testPath) {
      return `I've created a test for ${feature}. The test has been saved to ${testPath}. It's marked as ${complexity} complexity. Would you like me to run it now?`;
    } else {
      return `I've started creating a test for ${feature} using the ${data.model || 'Scribe'} agent. This ${complexity} complexity test should be ready in about 2 minutes.`;
    }
  }

  /**
   * Generate natural response for test execution
   */
  private generateTestExecutedResponse(data: any): string {
    const testPath = data.test_path || 'the test';
    const runnerResult = data.runner_result || {};

    if (runnerResult.passed) {
      const assertions = runnerResult.assertions_count || 0;
      const duration = runnerResult.duration_ms ? (runnerResult.duration_ms / 1000).toFixed(1) : '0';
      return `Great news! ${testPath} passed successfully with ${assertions} assertions verified. Execution took ${duration} seconds.`;
    } else {
      const errorMsg = runnerResult.error_summary || 'unknown error';
      return `The test ${testPath} failed with error: ${this.simplifyErrorMessage(errorMsg)}. I'm escalating this to the Medic agent for repair.`;
    }
  }

  /**
   * Generate natural response for bug fix
   */
  private generateBugFixedResponse(data: any): string {
    const testPath = data.test_path || 'the test';
    const medicResult = data.medic_result || {};

    if (medicResult.fix_applied) {
      const fixType = medicResult.fix_type || 'code fix';
      return `I've applied a ${fixType} to ${testPath}. The issue has been resolved. Would you like me to re-run the test to verify the fix?`;
    } else {
      return `I attempted to fix ${testPath}, but the issue requires human review. I'm adding this to the HITL queue for your attention.`;
    }
  }

  /**
   * Generate natural response for test validation
   */
  private generateTestValidatedResponse(data: any): string {
    const testPath = data.test_path || 'the test';
    const geminiResult = data.gemini_result || {};

    if (geminiResult.validation_passed) {
      const screenshots = geminiResult.screenshots_count || 0;
      const duration = geminiResult.execution_time_ms ? (geminiResult.execution_time_ms / 1000).toFixed(1) : '0';
      return `Perfect! ${testPath} has been validated in a real browser. All assertions passed with ${screenshots} screenshots captured. Execution took ${duration} seconds. This test is production-ready.`;
    } else {
      const issues = geminiResult.issues_found || [];
      const issueCount = issues.length || 0;
      return `The validation found ${issueCount} ${issueCount === 1 ? 'issue' : 'issues'} with ${testPath}. The test needs revision before it's production-ready.`;
    }
  }

  /**
   * Generate natural response for status inquiry
   */
  private generateStatusResponse(data: any): string {
    const sessionCost = data.session_cost || 0;
    const totalTasks = data.total_tasks || 0;
    const successfulTasks = data.successful_tasks || 0;
    const budgetStatus = data.budget_status?.status || 'ok';

    let response = `Session status: I've completed ${successfulTasks} out of ${totalTasks} tasks successfully. `;
    response += `Total cost is $${sessionCost.toFixed(2)}. `;

    if (budgetStatus === 'warning') {
      response += 'Budget is approaching the limit. ';
    } else if (budgetStatus === 'exceeded') {
      response += 'Warning: Budget has been exceeded. ';
    } else {
      response += 'Budget is looking good. ';
    }

    return response + 'What would you like to do next?';
  }

  /**
   * Generate natural response for full pipeline
   */
  private generatePipelineResponse(data: any): string {
    const stage = data.stage || 'unknown';
    const agentSummary = data.agent_summary || {};
    const totalAgents = data.total_agents_used || 0;

    if (stage === 'completed') {
      return `Excellent! The full pipeline completed successfully. ${totalAgents} agents worked together to create, validate, and verify the test. Everything is production-ready.`;
    } else if (stage === 'scribe_failed') {
      return `The pipeline stopped at the Scribe stage. I couldn't generate a valid test. Would you like me to try with a different approach?`;
    } else if (stage === 'critic_rejected') {
      return `The Critic agent rejected the test due to quality issues. This saved us the cost of running an unreliable test. Let me try creating a better version.`;
    } else if (stage === 'execution_failed') {
      const medicAttempts = Object.keys(agentSummary).filter(k => k.includes('medic')).length;
      return `The test execution failed after ${medicAttempts} repair attempts. I'm escalating this to the HITL queue for human review.`;
    } else {
      return `The pipeline is currently in progress at stage: ${stage}. ${totalAgents} agents have been involved so far.`;
    }
  }

  /**
   * Simplify error messages for voice communication
   */
  private simplifyErrorMessage(error: string): string {
    // Remove stack traces and technical details
    const simplified = error.split('\n')[0];

    // Replace technical terms with user-friendly language
    return simplified
      .replace(/TimeoutError|timeout/gi, 'timeout issue')
      .replace(/SelectorError|selector/gi, 'element not found')
      .replace(/NetworkError/gi, 'network connection issue')
      .replace(/AssertionError/gi, 'test assertion failed')
      .replace(/Error:/gi, '')
      .trim();
  }

  /**
   * Send response to user via voice synthesis
   */
  private async speakResponse(text: string): Promise<void> {
    // Add to conversation history
    this.conversationHistory.push({
      role: 'assistant',
      content: text
    });

    // Create response via Realtime API
    this.sendEvent({
      type: 'response.create',
      response: {
        modalities: ['text', 'audio'],
        instructions: text
      }
    });
  }

  // ==========================================================================
  // Audio Streaming
  // ==========================================================================

  /**
   * Stream audio input to Realtime API
   */
  streamAudioInput(audioData: Buffer): void {
    if (!this.isConnected || !this.ws) {
      console.warn('[Voice] Cannot stream audio - not connected');
      return;
    }

    const base64Audio = audioData.toString('base64');

    this.sendEvent({
      type: 'input_audio_buffer.append',
      audio: base64Audio
    });
  }

  /**
   * Commit audio buffer (end of user speech)
   */
  commitAudioInput(): void {
    this.sendEvent({
      type: 'input_audio_buffer.commit'
    });
  }

  /**
   * Clear audio buffer
   */
  clearAudioInput(): void {
    this.sendEvent({
      type: 'input_audio_buffer.clear'
    });
  }

  // ==========================================================================
  // Conversation Management
  // ==========================================================================

  /**
   * Add text message to conversation
   */
  addMessage(role: 'user' | 'assistant', content: string): void {
    this.conversationHistory.push({ role, content });

    this.sendEvent({
      type: 'conversation.item.create',
      item: {
        type: 'message',
        role,
        content: [
          {
            type: 'input_text',
            text: content
          }
        ]
      }
    });
  }

  /**
   * Create a response from the assistant
   */
  createResponse(): void {
    this.sendEvent({
      type: 'response.create',
      response: {
        modalities: ['text', 'audio']
      }
    });
  }

  /**
   * Cancel ongoing response
   */
  cancelResponse(): void {
    this.sendEvent({
      type: 'response.cancel'
    });
  }

  /**
   * Cancel ongoing operation (user interruption)
   */
  cancelOperation(): void {
    if (this.activeOperation) {
      const operation = this.activeOperation.operation;
      this.stopProgressTracking();

      this.emit('operation_cancelled', { operation });
      this.speakResponse(`I've cancelled the ${operation} operation. What would you like me to do instead?`);
    }
  }

  /**
   * Get current operation status
   */
  getOperationStatus(): { active: boolean; operation?: string; elapsed?: number; expected?: number } {
    if (!this.activeOperation) {
      return { active: false };
    }

    const elapsed = Date.now() - this.activeOperation.startTime;
    return {
      active: true,
      operation: this.activeOperation.operation,
      elapsed,
      expected: this.activeOperation.expectedDuration
    };
  }

  /**
   * Get conversation history
   */
  getConversationHistory(): Array<{ role: string; content: string }> {
    return [...this.conversationHistory];
  }

  /**
   * Clear conversation history
   */
  clearConversationHistory(): void {
    this.conversationHistory = [];
  }

  // ==========================================================================
  // Utility Methods
  // ==========================================================================

  /**
   * Send event to Realtime API
   */
  private sendEvent(event: any): void {
    if (!this.ws || !this.isConnected) {
      console.warn('[Voice] Cannot send event - not connected');
      return;
    }

    try {
      this.ws.send(JSON.stringify(event));
    } catch (error) {
      console.error('[Voice] Error sending event:', error);
      this.emit('send_error', error);
    }
  }

  /**
   * Check if connected
   */
  isActive(): boolean {
    return this.isConnected;
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Get audio configuration
   */
  getAudioConfig(): AudioConfig {
    return { ...this.audioConfig };
  }

  /**
   * Get all transcripts for current session from Redis
   */
  async getSessionTranscripts(): Promise<string[]> {
    if (!this.redisEnabled || !this.sessionId) {
      console.warn('[Voice] Redis not enabled or no session ID');
      return [];
    }

    return new Promise((resolve, reject) => {
      const redisCli = path.join(__dirname, 'redis_cli.py');
      const proc = spawn('python3', [
        redisCli,
        'get_transcripts',
        this.sessionId!
      ]);

      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (data: Buffer) => {
        stdout += data.toString();
      });

      proc.stderr.on('data', (data: Buffer) => {
        stderr += data.toString();
      });

      proc.on('close', (code: number | null) => {
        if (code !== 0) {
          console.warn('[Voice] Failed to retrieve transcripts:', stderr);
          resolve([]);
          return;
        }

        try {
          const transcripts = JSON.parse(stdout);
          resolve(Array.isArray(transcripts) ? transcripts : []);
        } catch (error: any) {
          console.warn('[Voice] Error parsing transcripts:', error.message);
          resolve([]);
        }
      });

      setTimeout(() => {
        proc.kill();
        reject(new Error('Get transcripts timeout'));
      }, 5000);
    });
  }
}

// ============================================================================
// Example Usage & CLI
// ============================================================================

/**
 * Example usage of VoiceOrchestrator
 */
async function example() {
  // Load API key from environment
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('OPENAI_API_KEY environment variable not set');
    process.exit(1);
  }

  // Create orchestrator
  const orchestrator = new VoiceOrchestrator({
    apiKey,
    voice: 'alloy',
    temperature: 0.8
  });

  // Set up event listeners
  orchestrator.on('connected', () => {
    console.log('Connected! Ready for voice commands.');
  });

  orchestrator.on('transcription', (text: string) => {
    console.log('User said:', text);
  });

  orchestrator.on('kaya_result', (result: KayaResult) => {
    console.log('Kaya result:', result);
  });

  orchestrator.on('audio_complete', (audio: Buffer) => {
    console.log('Received audio response:', audio.length, 'bytes');
    // Here you would play the audio to the user
  });

  orchestrator.on('error', (error: Error) => {
    console.error('Error:', error.message);
  });

  // Connect
  try {
    await orchestrator.connect();
    console.log('Voice orchestrator ready!');
  } catch (error) {
    console.error('Failed to connect:', error);
    process.exit(1);
  }
}

// Run example if this file is executed directly
if (require.main === module) {
  example().catch(console.error);
}

export default VoiceOrchestrator;
