---
description: Ensure the agent has fully read and understands the project's documentation system, structure, and rules (claude.md, SOPs, and doc index).
---
# Goal: Context Priming and Documentation Review

IMPORTANT: You are initiating a new task. Your primary goal is to **prime the context window** by reviewing all available repository documentation and established rules [4, 5].

1.  **Review Core Context:**
    *   Read the contents of the root **`claude.md`** file [5]. This file contains the initial prompt, general project instructions, style guidelines, repository etiquette, and common bash commands [5].
    *   Review all information previously saved to memory using the pound symbol (`#`) [6].

2.  **Access Documentation Structure:**
    *   Consult the **documentation index** (e.g., the `README` file within the `.agent` or `.doc` directory) first [7-9]. This index lists all available documents and helps provide a quick overview of the relevant documentations [7, 8].
    *   Prioritize accessing and understanding documents relating to **Project Structure**, **Database Schema**, and **API endpoints** contained within the system documentation folder [7, 10].

3.  **Review Implementation Plans and SOPs:**
    *   Search the task folder (e.g., `.agent/task` or `doc/task`) for existing **PRDs** (Product Requirement Documents) or **implementation plans** that are similar to the current request [11].
    *   Review **SOPs** (Standard Operating Procedures) to learn about common processes, how to integrate specific models (e.g., Replicate), or common mistakes to avoid [7, 12, 13].

4.  **Apply Context Management Rules:**
    *   Adhere to rules regarding the **continuous updating of project documentation** after features are implemented [8, 12].
    *   If a specific context file is used to maintain the project plan (e.g., `doc/task/context_sessions`), read this file first to understand the current state of the project before proposing changes [14, 15].

$arguments

---
Usage and Optimization Notes
This command is optimized for workflow by focusing on key contextual files that drive agent performance:
• claude.md: This file is crucial because it is automatically loaded into context for every conversation and sets the tone and rules for the agent.
• Documentation System: For complex codebases, the command directs the agent to the custom documentation system (often in an .agent folder). This practice is part of context engineering, ensuring that the agent reads a summarized snapshot of the codebase instead of attempting deep research across all files every time.
• Arguments Injection: The inclusion of $arguments allows you to pass specific instructions or file paths dynamically when running the command (e.g., /prime_repo_docs specific_feature.md).
• Agent Priming: By explicitly asking the agent to prioritize reading these documents, you are ensuring the "parent agent" has the full necessary context, which is key, as sub-agents operate in isolated contexts and communicate primarily through files.
