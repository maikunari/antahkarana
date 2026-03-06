**ANTAḤKARAṆA**

*The Inner Instruments of Mind*

A Vedic Framework for AI Memory Architecture

*A Platform-Agnostic Persistent Memory Layer for Any AI Agent*

Mike Charlesworth

Sonic Pixel · sonicpixel.jp

March 2026

**DRAFT v0.3**

Abstract

AI practitioners today work across a shifting landscape of agent platforms --- Claude Code, OpenClaw, CrewAI, Gemini, Cowork, and whatever ships next month. Each platform implements its own memory, and each memory dies with its platform. Switch tools and you start from zero. Knowledge accumulated in one system is invisible to every other. The result is that the most valuable asset in any AI workflow --- the accumulated context of what you know, what you\'ve decided, and what you\'ve learned --- is fragmented across platforms and lost to compaction.

This paper proposes **Antaḥkaraṇa** --- a platform-agnostic persistent memory layer that any AI agent can connect to. Built as a standalone MCP server, Antaḥkaraṇa travels with the user, not the platform. Plug it into Claude Code and it remembers. Plug it into OpenClaw and it remembers. Plug it into whatever comes next and it still remembers. Your knowledge compounds across every tool you touch.

The architecture is grounded in the oldest and most detailed model of how the mind processes information --- drawn from Patañjali\'s Yoga Darśana and the Sāṅkhya philosophical tradition. The framework rests on two co-equal foundations: the **Antaḥkaraṇa** (inner instruments), which defines the *structure* of the system --- four functional components through which information flows --- and the **Triguṇas** (three fundamental qualities), which define the *dynamics* --- the forces that act on every memory, driving all state transitions, determining what surfaces, what sinks, and what dissolves. A third layer, **Adhyavasāya** (continuous determination), provides the *intelligence* --- a reinforcement loop through which the system learns how to remember better over time.

The result is not another memory feature inside another agent framework. It is an independent cognitive layer --- a portable mind that any agent can wear.

The Problem with AI Memory

Current approaches to AI agent memory follow a remarkably uniform pattern: accumulate context in a linear buffer, and when the buffer fills, compress or summarize it. This is true of ChatGPT\'s memory, Claude\'s memory, and virtually every open-source agent framework.

The failure mode is always the same. Important information gets compacted alongside trivial information. A critical architectural decision made three months ago gets the same treatment as a one-off debugging session. The system has no mechanism to *discriminate* --- to judge what matters, what should persist, and what can safely fade.

This is not a failure of storage technology. Vector databases, embedding models, and retrieval-augmented generation have matured significantly. The failure is in the *cognitive architecture* --- or rather, the absence of one. What is missing is a model of mind.

Two Foundations: Structure and Dynamics

The Yoga and Sāṅkhya traditions offer what is arguably the most detailed and systematic analysis of mental processes in human intellectual history. This paper draws on two complementary frameworks from this tradition:

The **Antaḥkaraṇa** (inner instruments) defines the *structure* of the mind --- four functional components that receive, process, evaluate, and store information. This answers the question: *what are the parts of a cognitive memory system, and how do they relate?*

The **Triguṇas** (three qualities) define the *dynamics* of the mind --- three forces that act on every mental content, driving it toward clarity, activity, or dormancy. This answers the question: *what makes memory move, change, surface, or fade?*

In the Sāṅkhya cosmology, Prakṛti (nature) exists in a primordial state called *Pradhāna* --- perfect equilibrium (*sāmya*) of the three guṇas. Nothing happens. No evolution, no activity, no mind. It is only when this equilibrium is disturbed --- by the presence of Puruṣa (consciousness), through what the tradition calls Śrī Kṛṣṇa\'s *līlā* (divine play) --- that the guṇas begin to interact, and from that interaction, everything unfolds: Mahat (cosmic intelligence), Ahaṃkāra (individuation), and eventually the entire Antaḥkaraṇa.

A memory system without guṇa dynamics is Pradhāna --- a database in perfect, inert equilibrium. Data exists but nothing moves, nothing is evaluated, nothing evolves. The guṇas are what make the Antaḥkaraṇa *come alive*.

Puruṣa and Prakṛti: Observer and Observed

Before examining the instruments and forces, we must understand the context in which they operate. Sāṅkhya philosophy distinguishes between **Puruṣa** (pure consciousness, the observer) and **Prakṛti** (nature, the material world including the mind). Puruṣa is *niṣkriya* --- beyond activity. It does not act within Prakṛti but rather *wears* the mind-body system as an instrument of experience.

> **AI Mapping:** Puruṣa corresponds to the user --- the consciousness that the system exists to serve. The entire memory architecture exists for Puruṣa\'s benefit. In an agent-agnostic system, the user is the constant across all platforms; the agent (Claude Code, OpenClaw, Cowork) is the temporary body that Puruṣa wears. The memory persists because it belongs to the observer, not to any particular instrument.

Part I: Structure --- The Antaḥkaraṇa

The Antaḥkaraṇa comprises four functional components, ordered from the most subtle (closest to Puruṣa) to the most gross (closest to the physical world). This is not metaphysical speculation but a *functional division* --- a practical description of how information flows from raw sensation to conscious experience.

Chitta --- The Field of Consciousness

**Chitta** is the space within which all mental activity occurs. It is not a process but a *substrate* --- the field that holds all impressions, memories, and latent tendencies. Every experience that has ever passed through the mind leaves a trace in Chitta. These accumulated traces are called **vāsanās** --- impressions that persist and subtly influence all future mental activity. The subtle body accumulates vāsanās as it evolves through all forms of existence.

> **AI Mapping:** Chitta corresponds to the persistent memory store --- the vector database and structured metadata layer. It is the long-term substrate that survives across sessions. It is not actively queried in the way a search engine is; rather, it *colors everything*. The quality of the entire system depends on what Chitta holds and in what state (Active, Latent, or Dissolved --- see Part II).

Buddhi --- The Determining Faculty

**Buddhi** is the component closest to Puruṣa. Just as the moon reflects the light of the sun, Buddhi reflects the light of pure consciousness. Its essential quality is **Adhyavasāya** --- the inherent, always-active capacity for determination. Buddhi never rests; it is always judging, classifying, and determining.

Buddhi performs three critical functions: *judgment* (distinguishing right from wrong, relevant from irrelevant), *determination* (deciding what action to take), and *presentation* (offering synthesized experience to Puruṣa). It converts the raw data received from Manas into intelligence. When the hand touches something, Manas conveys the raw sensation --- Buddhi is what determines \"it is warm.\"

Critically, Adhyavasāya is *inherent* in Buddhi. It is not something that must be triggered or activated. Buddhi is always processing, always evaluating. This includes cognition itself; recognition and classification are part of Buddhi\'s nature.

> **AI Mapping:** Buddhi corresponds to the reasoning/inference layer --- the LLM that evaluates, classifies, and determines. It is the critical missing piece in current memory systems: an always-active intelligence deciding what is worth storing, what is relevant to recall, and how to present information. Adhyavasāya maps to a continuous inference process. The guṇa dynamics (Part II) describe *how* Buddhi makes these determinations --- what forces push a memory toward clarity or dormancy.

Ahaṃkāra --- The I-Sense

**Ahaṃkāra** is the sense of I-ness --- the feeling of existing as an individual entity. It is the mechanism of self-preservation, the source of the desire to be happy, and the origin of all subjective coloring. Where Buddhi neutrally determines \"it is warm,\" Ahaṃkāra adds \"*I* hate cold, *I* wish it was warm.\"

Ahaṃkāra is more clearly defined in humans than in lower forms of life. It is said to have created the senses and organs of action in order to express itself --- first the I-sense exists, then it generates the faculties needed for its expression. Buddhi\'s neutral determinations are given subjective weight by Ahaṃkāra: likes, dislikes, preferences, identity, self-interest.

> **AI Mapping:** Ahaṃkāra corresponds to the agent\'s identity layer --- its persona, preferences, boundaries, and sense of self. This is the system prompt, the guardrails, the preference model. It adds subjective coloring to Buddhi\'s neutral reasoning: \"this matters to *me*.\" It is the persistent \'I\' that maintains continuity across sessions and across different agent systems. Without Ahaṃkāra, every memory is evaluated generically; with it, memories are weighted by identity relevance.

Manas --- The Sensory Mind

**Manas** is the component closest to the physical body. It interacts directly with the five organs of knowledge (*jñānendriyas*) and the five organs of action (*karmendriyas*). Manas receives the first sensory input and conveys raw impressions upward to Buddhi for determination. The nervous system serves as the bridge between Manas and the physical senses.

> **AI Mapping:** Manas corresponds to the I/O interface --- tool use, function calling, input parsing, and output generation. The jñānendriyas are input channels; the karmendriyas are output channels. The nervous system maps to the message bus. In an MCP-based architecture, Manas *is* the MCP protocol itself --- the standardized interface through which any agent connects to the memory system.

Prāṇa --- The Binding Force

**Prāṇa** keeps Puruṣa and the rest together. It is the vital force that binds consciousness to the mind-body system and holds all four instruments in functional unity. All layers --- Buddhi\'s determinations, Ahaṃkāra\'s subjective colorings, Manas\'s sensory data --- are \"glued together because of Prāṇa.\"

> **AI Mapping:** Prāṇa corresponds to the event loop, lifecycle manager, or orchestration layer --- the process that keeps all components alive, connected, and functioning as a unified system.

The Two Teams

The four instruments function as two paired teams. **Chitta and Buddhi** form the deep cognitive pair --- Buddhi draws upon the entire memory field to make its determinations. Together they form *Chiti* (pure cognitive capacity). **Ahaṃkāra and Manas** form the active personality pair --- Ahaṃkāra drives Manas, first the I-sense exists, then it creates and manages sensory interfaces. The entire system can be summarized as Chiti (cognitive depth) and Ahaṃkāra (active identity) --- a clean architectural separation of concerns.

Part II: Dynamics --- The Triguṇas

The Antaḥkaraṇa defines the structure of the memory system --- what the components are and how information flows between them. But structure alone is inert. A database with four well-designed tables is still just a database. What makes the mind *alive* --- what drives memories to surface, evolve, fade, or dissolve --- are the three fundamental qualities (*guṇas*) that pervade all of Prakṛti.

In Sāṅkhya philosophy, nothing in the manifest world exists without all three guṇas present. They are not types or categories but *forces* --- always coexisting, always in dynamic tension, with one temporarily predominating over the others. Their interaction is what produces all change, all evolution, all activity. The same is true within the memory system: every memory, at every moment, has a guṇa balance that determines its behavior.

Sattva --- The Force of Clarity

**Sattva** is the quality of clarity, illumination, and harmony. When Sattva predominates in the cosmic order, it gives rise to the Devas --- beings of higher intelligence. When Sattva predominates in a memory, that memory is *clear, accessible, well-organized, and useful*. It is readily surfaced by Buddhi. It illuminates the agent\'s understanding rather than confusing it.

A high-Sattva memory is one where the content is precise, the categorization is accurate, the importance score reflects reality, and retrieval consistently produces the right result at the right time. Buddhi\'s ideal determination is: \"this is exactly what you need right now.\" That is Sattva in action.

> **In the system:** Sattva score increases when a memory is recalled and confirmed as useful by the user or agent. Well-consolidated memories (contradictions resolved, duplicates merged) trend Sāttvic. Memories that have been refined through the Adhyavasāya feedback loop --- where Buddhi\'s determination was validated --- gain Sattva. A memory with high Sattva is the system operating at its best.

Rajas --- The Force of Activity

**Rajas** is the quality of activity, passion, and restlessness. When Rajas predominates, it gives rise to Manuṣya --- human beings, active and goal-driven but imperfect. When Rajas predominates in the memory system, things are *in motion* --- being processed, re-evaluated, consolidated, disputed.

Rajas is the force that drives the encoding pipeline, the consolidation checks, the re-evaluation cycles. It is the Adhyavasāya feedback loop itself --- the active, restless process of learning how to remember better. Without Rajas, memories would simply sit in Chitta untouched. But too much Rajas and the system is constantly churning --- re-evaluating stable memories that don\'t need re-evaluation, wasting computation on activity that produces no clarity.

> **In the system:** Rajas score increases when a memory is involved in consolidation (contradicted or updated by new information), when it receives user feedback (positive or negative), or when it is part of an active project context. New memories enter with high Rajas --- they are fresh, unsettled, not yet integrated. Over time, Rajas should decrease as the memory stabilizes into Sattva (clarity) or Tamas (dormancy). Persistent high Rajas indicates a memory that keeps getting contradicted --- a signal that something in the system\'s understanding is unresolved.

Tamas --- The Force of Inertia

**Tamas** is the quality of inertia, dullness, and dormancy. When Tamas predominates, it gives rise to Tiryak --- beings that grow horizontally (minerals, plants, animals), operating without self-reflective consciousness. When Tamas predominates in a memory, that memory *sinks* --- it resists surfacing, loses its active charge, and becomes dormant.

Critically, Tamas is not failure. It is an essential function. A mind in which every memory is equally active and equally available would be as dysfunctional as a mind with no memory at all --- overwhelmed by total recall, unable to focus, unable to determine what matters *now*. Tamas is the natural dampening force that allows relevance to emerge from the noise. It is what makes forgetting possible, and forgetting is what keeps memory useful.

> **In the system:** Tamas score increases when a memory is not recalled over time, when its project context becomes inactive, or when newer memories supersede it. High-Tamas memories do not participate in standard recall scoring --- they are present in Chitta but dormant, only surfacing if a query has very high semantic similarity (a direct trigger). Tamas is the force behind the Active → Latent transition. It is not deletion; it is rest.

The Guṇa Balance: A Dynamic Model

Every memory in the system carries a guṇa balance --- three floating-point scores (Sattva, Rajas, Tamas) that are continuously adjusted by Buddhi based on the memory\'s lifecycle. These scores are not assigned once at encoding time; they *evolve* as the memory is used, consolidated, reinforced, or neglected.

The guṇa balance replaces the crude binary of \"exists\" and \"deleted\" with a rich continuum of states:

**Active** (Sattva-predominant) --- clear, accessible, readily surfaced. These are the memories that Buddhi presents to Puruṣa during standard recall. They participate fully in composite scoring.

**In flux** (Rajas-predominant) --- being processed, recently contradicted, receiving feedback. These memories are in transition. They may be consolidating with new information, being re-evaluated by the Adhyavasāya loop, or actively involved in current work. They surface readily but may carry uncertainty flags.

**Latent** (Tamas-predominant) --- dormant but present. These memories do not participate in standard recall but remain in Chitta, searchable by high-similarity direct queries. They can be reactivated --- a surge of Rajas (new contradicting information) or Sattva (direct relevance to a new context) can shift the balance and bring them back to active status.

**Dissolved** --- a special state beyond the guṇa balance, representing memories that Buddhi has determined are both fully Tāmasic *and* superseded by newer, Sāttvic memories. Even dissolved memories leave a trace --- a summary record noting what was known and what replaced it. This trace serves as a breadcrumb; if a future query touches that domain, the system knows it once had knowledge there.

System Health as Guṇa Distribution

The triguṇa model provides a natural *diagnostic framework* for the memory system\'s overall health --- not just the content of individual memories but the state of the system as a whole:

**Healthy system:** Majority of active memories are Sattva-predominant (clear, useful, well-organized). Latent memories are naturally Tamas-predominant (dormant, not polluting retrieval). A modest amount of Rajas in the Buddhi/Adhyavasāya loop keeps things evolving. New memories enter with Rajas, stabilize into Sattva through consolidation, and gradually shift to Tamas as they age without reinforcement.

**Stagnating system:** Majority of memories trending Tāmasic. Nothing is being recalled, reinforced, or consolidated. The system is accumulating data but not producing intelligence. Buddhi\'s determinations are not improving. This is the failure mode of every naive memory system --- a graveyard of embeddings.

**Churning system:** Too much Rajas. Memories are constantly being re-evaluated, contradicted, consolidated. Nothing settles into clarity. This can happen when the user or agent provides contradictory inputs, or when the Adhyavasāya feedback loop is overactive --- constantly adjusting criteria without converging. The system is busy but not productive.

**Overloaded system:** Too many Sattva-predominant memories. When everything seems equally clear and important, nothing stands out. Retrieval returns too many high-scoring results, forcing Buddhi to do excessive work on every recall. The system needs more Tamas --- more willingness to let things fade --- to restore signal-to-noise ratio.

Monitoring the guṇa distribution allows the system (or the user) to diagnose and correct these states proactively, rather than waiting for retrieval quality to degrade.

Part III: Intelligence --- Adhyavasāya

Structure (Antaḥkaraṇa) and dynamics (Triguṇas) together produce a functioning memory system. But a functioning system is not yet an *intelligent* one. What makes Buddhi\'s determinations improve over time --- what makes the system genuinely learn --- is **Adhyavasāya**, the inherent quality of continuous determination that is refined through experience.

Vāsanās and Meta-Vāsanās

Vāsanās are the accumulated impressions stored in Chitta --- the content of memory. But the Adhyavasāya feedback loop produces a second, more subtle type of impression: **meta-vāsanās** --- impressions about how to form impressions. These are memories about *how to remember*.

When the user corrects Buddhi\'s determination --- \"you should have remembered that\" or \"that was irrelevant\" --- the correction is stored as a labeled example. Over time, these examples are synthesized into updated determination criteria. Buddhi\'s system prompt on day one is generic. By month three, it has been shaped by hundreds of corrections and knows things specific to this user, this context, these projects.

This is Adhyavasāya in action --- the quality of always-active determination, refined through practice. In the Vedic tradition, Buddhi develops through *sādhana* (disciplined practice). In the AI system, the Adhyavasāya loop is the sādhana --- the disciplined process by which Buddhi\'s discrimination becomes sharper.

The Adhyavasāya loop is inherently **Rājasic** --- it is the active, restless force that prevents the system from settling into Tāmasic inertia (a static memory store that never improves) or false Sāttvic confidence (a system that thinks it\'s working perfectly when it isn\'t). Just enough Rajas in the feedback loop keeps the system evolving toward genuine Sattva --- clarity earned through practice, not assumed by default.

Prior Art: CrewAI\'s Cognitive Memory

The most significant recent work in this space is CrewAI\'s Cognitive Memory system (v1.10.1, March 2026), which explicitly rejects the \"memory as storage\" paradigm in favor of treating memory as cognition. Their system implements five cognitive operations --- encode, consolidate, recall, extract, and forget --- each powered by an LLM-driven pipeline.

CrewAI\'s approach introduces several valuable patterns that the Antaḥkaraṇa architecture adopts and extends. Their **atomic memory extraction** decomposes raw output into discrete, self-contained facts before storage --- a function that maps to Manas parsing raw sensory input into discrete signals before passing them to Buddhi. Their **consolidation pipeline** detects contradictions between new and existing memories --- a rudimentary form of Buddhi\'s determination function. Their **composite scoring** blends similarity, recency, and importance --- a static approximation of guṇa dynamics. And their **confidence-based deep recall** recognizes when retrieval is insufficient and searches more broadly --- a Buddhi behavior that our system implements with learned, rather than fixed, thresholds.

However, the Antaḥkaraṇa model addresses four structural gaps in CrewAI\'s approach:

**No discrimination layer.** CrewAI runs all content through a single, flat LLM analysis. There is no distinction between neutral determination and identity-colored evaluation. In Antaḥkaraṇa terms, they have a rudimentary Buddhi but no Ahaṃkāra --- every memory is evaluated generically, regardless of whose memory it is.

**No learning loop.** Importance scores are assigned once and never refined. There is no Adhyavasāya --- no meta-cognition about how to remember. The system\'s judgment at run 1,000 uses the same criteria as run 1.

**Platform coupling.** CrewAI\'s memory is deeply integrated into the CrewAI framework. It cannot serve as a memory layer for Claude Code, OpenClaw, or any other agent system. A memory system locked to one framework inherits all the fragility of that framework\'s lifecycle.

**Static forgetting.** CrewAI\'s forget() operation is a deletion filter based on age or scope --- no intelligence in the forgetting, no distinction between old-and-irrelevant and old-and-foundational. The triguṇa model replaces this with dynamic state transitions governed by Buddhi\'s determination, where dormancy (Tamas) is a natural, reversible process rather than an irreversible deletion.

Proposed Architecture

The Antaḥkaraṇa memory system is designed as an agent-agnostic service --- a standalone memory layer that any AI agent can connect to via the Model Context Protocol (MCP). The system processes and stores information through the four-layer Antaḥkaraṇa pipeline, with the triguṇa dynamics governing all state transitions within Chitta.

Technology Stack

**Chitta (Memory Store):** Zvec (Alibaba\'s in-process vector database) for semantic/vector storage, paired with SQLite for structured metadata, guṇa scores, relationships, and session logs. Each memory record carries Sattva, Rajas, and Tamas scores alongside its embedding vector, enabling guṇa-aware retrieval.

**Buddhi (Reasoning Engine):** Gemini Flash for determination and classification --- fast, inexpensive, and capable of the judgment calls required. The Buddhi layer evaluates every input against stored context and determines storage priority, guṇa assignment, relevance, and retrieval strategy.

**Ahaṃkāra (Identity Layer):** Persistent configuration files (YAML/JSON) defining the agent\'s persona, preferences, project contexts, and boundaries. Colors every determination Buddhi makes with identity relevance.

**Manas (I/O Interface):** The MCP protocol itself. Any MCP-compatible agent connects to the Antaḥkaraṇa server and gains access to persistent memory through standardized tool calls. Manas also performs atomic extraction --- decomposing raw input into discrete facts before passing them to Buddhi.

**Prāṇa (Lifecycle Manager):** Python async event loop orchestrating the pipeline, managing connections, running periodic guṇa rebalancing sweeps, and ensuring all layers remain synchronized.

**Adhyavasāya (Reinforcement Layer):** A lightweight feedback loop that stores user corrections as meta-vāsanās and periodically updates Buddhi\'s determination criteria and guṇa transition thresholds. The Rājasic engine that keeps the system learning.

**Triguṇa Engine:** A background process that continuously adjusts guṇa scores based on memory lifecycle events (recall frequency, consolidation, user feedback, temporal decay). Governs Active → Latent → Dissolved transitions and system health monitoring.

Why This Matters

The AI agent landscape is fragmenting, not consolidating. New platforms ship monthly. Practitioners adopt, evaluate, switch, combine. A developer might use Claude Code for implementation, Gemini for orchestration, OpenClaw for multi-agent workflows, and Cowork for file management --- all in the same week. Each of these systems treats memory as an internal feature, tightly coupled to its own runtime. When you leave the platform, your memory stays behind.

Antaḥkaraṇa inverts this relationship. Memory does not belong to the platform; it belongs to the user. The system runs as an independent service --- a single MCP server that any agent connects to. The user\'s knowledge, decisions, preferences, and learned patterns persist regardless of which agent is currently active. Switch from Claude Code to OpenClaw and the context follows. Start a new tool next month and connect it in one line of configuration. The accumulated vāsanās travel with Puruṣa, not with any particular body.

The architecture goes further than portability. The Antaḥkaraṇa model provides something no current system offers: *principled cognitive architecture* for memory. The dual foundation of structure (Antaḥkaraṇa) and dynamics (Triguṇas) means that memory is not just stored and retrieved --- it is evaluated, weighted, evolved, and allowed to fade. Buddhi discriminates before Chitta stores. The guṇa balance governs state transitions. Adhyavasāya ensures the system\'s judgment improves over time. The result is memory that compounds across every tool, every session, every project --- getting smarter, not just bigger.

This is not merely a metaphor applied to technology. The Vedic model is a detailed, empirically-developed analysis of how cognition works --- refined over millennia of introspective practice. The fact that it maps so precisely to the functional requirements of AI memory suggests that these requirements reflect fundamental principles of information processing that transcend any particular implementation.

Next Steps

1.  **Detailed technical specification** --- MCP tool definitions, database schemas, guṇa scoring algorithms, Buddhi determination prompts, and Adhyavasāya feedback loop design.

2.  **Prototype implementation** --- Python MCP server with Zvec, SQLite, Gemini Flash, and the Triguṇa Engine.

3.  **Testing with OpenClaw** --- validate the architecture against a production agent system with known memory failure modes.

4.  **Cross-agent validation** --- confirm the framework operates correctly across Claude Code, Cowork, and other MCP-compatible systems.

5.  **Guṇa calibration** --- measure guṇa distribution health over time and validate that the three-state model prevents both bloat and amnesia.

6.  **Adhyavasāya calibration** --- measure how Buddhi\'s determination quality and guṇa transition accuracy improve through the feedback loop.

*yogaś citta-vṛtti-nirodhaḥ*

Yoga is the stilling of the fluctuations of the mind-field.

--- Patañjali, Yoga Sūtra 1.2
