# Chapter Writer Skill

This skill provides guidance for writing chapters in "Building AI Agents from Scratch with Python."

## When to Use This Skill

Trigger this skill when:
- Drafting new chapter content
- Expanding existing chapter sections
- Updating chapter text to match code changes
- Writing introductions, explanations, or summaries
- Creating exercises and learning objectives

## Chapter Structure Template

Every chapter MUST follow this exact structure:

### 1. Introduction (1-2 paragraphs)
- **Hook**: Engaging opening that shows why this matters
- **Context**: How this builds on previous chapters
- **Preview**: What the reader will build/learn
- **Prerequisites**: Specific chapters or concepts needed

Example:
```markdown
# Chapter X: [Title]

You've built [previous concept], but there's a problem. [Real-world limitation].
In this chapter, we'll solve that by [new concept]. By the end, you'll have
[concrete outcome] and understand [core principle].

We'll build on the [previous concept] from Chapter X and introduce [new elements].
```

### 2. Learning Objectives (Bulleted list)
Specific, measurable goals. Use action verbs.

Example:
```markdown
## Learning Objectives

By the end of this chapter, you will be able to:
- Implement [specific technique] using [specific approach]
- Understand the trade-offs between [option A] and [option B]
- Build a [specific system] that can [concrete capability]
- Explain why [concept] is important for [use case]
```

### 3. Main Content (Varies by complexity)

**Structure the content in logical sections:**

#### Concepts First (2-4 pages)
- Explain the core ideas clearly
- Use analogies when helpful (but don't overdo it)
- Include diagrams for complex relationships
- Define all new terminology
- Explain the "why" before the "how"

#### Implementation Second (4-8 pages)
- Show complete, working code FIRST
- Then explain line by line for complex parts
- Build incrementally - show the evolution
- Highlight key design decisions
- Explain trade-offs explicitly

**Code Integration Guidelines:**
- Code comes BEFORE long explanations
- Every code block must be complete and runnable
- Reference the example file location
- Include inline comments for learning moments
- Don't over-comment obvious code

Example:
```markdown
## Building the Message Loop

Let's start with a simple implementation (from `example_01.py`):

\```python
def message_loop(system_prompt: str) -> None:
    """Run a simple agent message loop."""
    messages = []

    while True:
        # Get user input
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break

        # Add to messages
        messages.append({"role": "user", "content": user_input})

        # Call API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=messages
        )

        # Add response to history
        assistant_message = response.content[0].text
        messages.append({"role": "assistant", "content": assistant_message})

        print(f"Assistant: {assistant_message}")
\```

This loop maintains conversation history by appending each exchange to the
`messages` list. The system prompt guides the agent's behavior, while the
message history provides context for multi-turn conversations.

Notice we're keeping messages in memory. This works for short conversations,
but in Chapter X we'll add persistence for longer interactions.
```

### 4. Common Pitfalls (2-3 items)

Highlight specific mistakes to avoid:

```markdown
## Common Pitfalls

### 1. Forgetting to Copy Message History
❌ **Don't** mutate the original messages list:
\```python
messages.append(...)  # Mutates original!
\```

✅ **Do** copy before modifying:
\```python
messages = messages.copy()
messages.append(...)
\```

### 2. Ignoring Error Handling
Without proper error handling, your agent will crash on API errors. Always wrap
API calls in try-except blocks (see `example_02.py`).

### 3. Hardcoding Model Parameters
Different tasks need different settings. Extract model, max_tokens, and
temperature into configuration (covered in Chapter X).
```

### 5. Practical Exercise (1-2 pages)

**Exercise Structure:**
- Clear task description
- Specific requirements
- Hints if needed
- Solution provided in code folder

Example:
```markdown
## Practical Exercise

### Task: Add Conversation Memory Limits

Modify the message loop to keep only the last 10 exchanges.

**Requirements:**
1. Maintain the full conversation internally
2. Only send the last 10 messages to the API
3. Always include the system prompt
4. Print a message when trimming occurs

**Hints:**
- Use list slicing: `messages[-10:]`
- Count exchanges, not individual messages
- Remember that each exchange = 2 messages (user + assistant)

**Solution**: See `exercise_memory_limit.py` in the code folder.

**Extension**: Implement token-based limiting instead of message counting
(you'll learn token counting in Chapter X).
```

### 6. Key Takeaways (Bulleted summary)

```markdown
## Key Takeaways

- The message loop is the foundation of any conversational agent
- Maintaining conversation history enables multi-turn interactions
- System prompts provide consistent behavioral guidance
- Error handling is essential for production agents
- Memory management becomes critical for long conversations
- [One more key point specific to the chapter]
```

### 7. What's Next (1 paragraph)

Preview the next chapter and show progression:

```markdown
## What's Next

Our message loop works well for simple conversations, but what happens when
the agent needs to DO something? In Chapter X, we'll add tools to give our
agent real capabilities - from searching the web to querying databases.
You'll learn how function calling works and build a tool-enabled agent.
```

## Writing Standards

### Voice & Tone

**Conversational but Professional**
- Write like explaining to a senior developer over coffee
- Avoid academic stuffiness, but maintain technical precision
- Use "we" and "you" to create connection
- Be direct and clear - no fluff

✅ Good examples:
- "Let's build a simple agent loop. We'll start with the core message handling."
- "You might wonder why we're not using async here. The reason is clarity - we'll add async in Chapter X when we need concurrency."
- "This approach trades some flexibility for simplicity, a worthwhile trade-off when learning."

❌ Avoid:
- "It should be noted that the implementation of asynchronous patterns..."
- "One could potentially consider the utilization of..."
- "This is absolutely amazing and will revolutionize your code!"

### Technical Writing Guidelines

**Active Voice**
✅ "The agent processes the request"
❌ "The request is processed by the agent"

**Present Tense for Code**
✅ "The function returns a list of messages"
❌ "The function will return a list of messages"

**Clarity Over Cleverness**
✅ "Store the conversation history in a list"
❌ "Leverage a list-based persistence mechanism for conversational context"

**Always Explain Trade-offs**
```markdown
We're using a simple list here rather than a database. This keeps the code
clear for learning, but in production you'd want persistent storage. We'll
explore database-backed memory in Chapter X.
```

## Content Quality Checklist

Before considering a chapter complete, verify:

### Structure
- [ ] Follows the 7-part template exactly
- [ ] Smooth transitions between sections
- [ ] Clear narrative arc from intro to summary
- [ ] Exercises build directly on chapter content
- [ ] References to previous/future chapters are accurate

### Technical Content
- [ ] All code examples are referenced correctly
- [ ] Code file names match what's described
- [ ] Example numbers are sequential
- [ ] Exercises have solutions in the code folder
- [ ] Prerequisites are clearly stated

### Writing Quality
- [ ] Active voice dominates
- [ ] Present tense for code descriptions
- [ ] Conversational but professional tone
- [ ] No unnecessary jargon
- [ ] Trade-offs explicitly explained
- [ ] "Why" explained, not just "how"

### Consistency
- [ ] Terminology matches previous chapters
- [ ] References the correct AugmentedLLM or Agent class if applicable
- [ ] Builds on established patterns appropriately
- [ ] Icons used correctly (💡 ⚠️ 🔧 📚)

### Progressive Complexity
- [ ] Assumes knowledge from previous chapters
- [ ] Introduces ONE new major concept
- [ ] Doesn't jump ahead to concepts from later chapters
- [ ] Prepares for concepts in next chapters

## Common Issues to Fix

### 1. Over-Explaining Simple Code
❌ "We import the requests library on line 1, which is a Python package for making HTTP requests..."
✅ Let obvious code speak for itself, or use brief inline comments

### 2. Under-Explaining Complex Code
❌ Showing complex async/await code without explanation
✅ "The @retry decorator catches rate limit errors and waits before retrying. This implements exponential backoff - doubling the wait time after each failure."

### 3. Inconsistent Terminology
- Choose ONE term and stick with it
- "message history" OR "conversation context" - not both
- Define terms clearly on first use
- Check previous chapters for established terminology

### 4. Missing Context
Every code example needs:
- Location referenced: "See `example_01.py`"
- Connection to previous code: "Building on our AugmentedLLM from Chapter 14..."
- Full working example, not fragments

### 5. Weak Transitions
❌ "Now we'll talk about error handling."
✅ "Our agent works great in happy-path scenarios. But what happens when the API is down? Let's add error handling to make our agent production-ready."

## Chapter Type Variations

### Concept Chapters (Odd-numbered in workflows)
Focus on the "what" and "why":
- More explanation, less code
- Diagrams and analogies
- Theory that supports practice
- Sets up the implementation chapter

### Implementation Chapters (Even-numbered in workflows)
Focus on the "how":
- Code-first approach
- Step-by-step building
- Multiple examples showing progression
- Practical exercises

### Hybrid Chapters (Parts 1, 2, 4, 5)
Balance concept and implementation:
- Introduce concept briefly
- Show implementation
- Explain as you build
- Emphasize practical application

## Progressive Dependencies

**Know what readers can use at each stage:**

- **Ch 1-6**: Basic API calls only
- **Ch 7-13**: Function calling patterns
- **Ch 14+**: Can import and use `AugmentedLLM` class
- **Ch 15-25**: Can use workflow patterns
- **Ch 26-33**: Building toward the `Agent` class
- **Ch 34+**: Can use testing and production patterns

When writing, reference these dependencies:
```python
# Chapter 20+ can do this:
from chapter_14.code.augmented_llm import AugmentedLLM

# Chapter 35+ can do this:
from chapter_33.code.agent import Agent
```

## Icon Usage in Prose

Use icons consistently (NOT in code comments):

- 💡 **Tips and best practices**: "💡 Tip: Use async for I/O-bound operations"
- ⚠️ **Warnings and pitfalls**: "⚠️ Warning: Never hardcode API keys"
- 🔧 **Practical exercises**: "🔧 Exercise: Modify the loop to..."
- 📚 **Further reading**: "📚 Read more about ReAct in the original paper"

## Examples of Good Chapter Writing

### Strong Opening
```markdown
# Chapter 16: Prompt Chaining

You've built agents that respond to single prompts. But what about tasks that
need multiple steps? Write an essay. Analyze data, then create a report.
These require chaining prompts together, where each step builds on the last.

In this chapter, you'll learn prompt chaining - a fundamental agentic workflow
that breaks complex tasks into sequential steps. By the end, you'll build a
research agent that gathers information, analyzes it, and creates a summary.

We'll use the AugmentedLLM from Chapter 14 and introduce the concept of
specialized prompts for each step.
```

### Strong Explanation with Code
```markdown
## Why Prompt Chaining Works

Large language models excel at focused tasks. Ask for an essay and analysis
in one prompt, you'll get mixed results. But split it into steps:

1. Research: "Find information about X"
2. Analyze: "Analyze this information for patterns"
3. Synthesize: "Create a summary from this analysis"

Each step produces better output than a single complex prompt.

Let's see this in action (from `example_01_simple_chain.py`):

\```python
def research_chain(topic: str) -> str:
    """Chain prompts to research a topic."""

    # Step 1: Generate research questions
    questions_prompt = f"Generate 3 specific research questions about {topic}"
    questions = call_llm(questions_prompt)

    # Step 2: Research each question
    research_prompt = f"Research these questions:\n{questions}"
    research = call_llm(research_prompt)

    # Step 3: Synthesize findings
    synthesis_prompt = f"Synthesize this research into key insights:\n{research}"
    insights = call_llm(synthesis_prompt)

    return insights
\```

Each call builds on the previous output. The final result is more focused and
comprehensive than a single "research this topic" prompt would produce.
```

## Reference Materials

**Always check these before writing:**
- `ai_agents/skills/PROJECT_INSTRUCTIONS.md` - Complete writing standards
- `ai_agents/skills/OUTLINE.md` - Chapter structure and dependencies
- `ai_agents/CLAUDE.md` - Technical architecture and patterns

**For architecture patterns:**
- `chapter-14-building-the-complete-augmented-llm/code/augmented_llm.py`
- `chapter-33-the-complete-agent-class/code/agent.py`

---

**Remember**: Every chapter should teach ONE core concept clearly, with working code that readers can run immediately. Clarity and practicality above all.
