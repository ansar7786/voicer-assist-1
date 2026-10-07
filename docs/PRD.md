SIH26097 Build Roadmap: Manual Steps vs Agent Steps
Step-by-step build guide for the Live Voice Livelihood Pathway Engine | 6 October 2026 | Companion to docs/PRD.md
1. How to use this document
The PRD says what to build. This document says in what order, what you do by hand, and what you tell the coding agent. Work top to bottom. Do not start a phase until the previous phase's verification passes.
Label	Meaning
YOU	Manual work. The agent cannot or should not do it (keys, real data, speaking, testing, decisions).
AGENT	Work you delegate to the Antigravity agent using the prompt given.
GATE	A decision point. Do not continue until it is settled.
VERIFY	A fact to check in official docs. Do not trust memory, including mine.
1.1 Two different models. Do not mix them up
	Coding model	Live voice model
What it does	Writes your code inside Antigravity	Talks to the user inside your running app
Where you set it	Model dropdown in Antigravity	GEMINI_LIVE_MODEL in .env
How you choose	Pick whatever your dropdown shows. I cannot confirm a model called Gemini 3.8 Flash exists	Find the current Live or native-audio model id in Google's Live API docs (Step 0)
Flash-class coding models are fast but can drift on large multi-file work. For Phases 3, 4 and 5 (live bridge, tools, what-if), switch to the strongest model your dropdown offers if there is one. Use the fast model for Phases 1, 2, 6 and 7.
1.2 The golden rules
1.	One phase per agent session. Never ask for two phases at once.
2.	Always start the prompt with: read docs/PRD.md first.
3.	The agent never sees your real API key. You put it in .env yourself.
4.	Nothing hardcoded: no keys, model names, pathways, diffs, badges or numbers.
5.	Commit after every phase that passes verification. If a phase goes bad, you can roll back.
6.	You run the verification yourself. Do not accept the agent saying it works.

2. Timeline at a glance
Adjust to your real deadline. If time is short, protect Phases 0 to 5 and keep Phase 6 small.
Phase	Name	Rough effort	Protect if short?
Step 0	Manual setup	1 to 2 hours	Yes
0	Live voice gate	Half day	Yes (blocks everything)
1	Skeleton	2 to 3 hours agent, data work runs in parallel	Yes
2	Engine first (no LLM)	1 day	Yes
3	Live bridge	1 day	Yes
4	Live profile via tools	1 day	Yes
5	Live pathways and what-if	1 day	Yes
6	Official view	Half day	Keep small
7	Fallbacks and polish	1 day	Cached replay and typed mode are the minimum
8	Recording day	Half day	Yes
Start the data work (NSQF rows, adjacency, sample data) on day one and run it in parallel. It is the slowest manual task and it decides your credibility.

3. Step 0: Manual setup (no agent yet)
3.1 Install tools (YOU)
•	☐ Python 3.11 or newer
•	☐ Node 20 or newer
•	☐ Git
•	☐ Google Chrome (best AudioWorklet and mic support)
•	☐ Antigravity
•	☐ Headphones (mandatory from Phase 0, prevents the model hearing itself)
•	☐ Phone hotspot as backup internet
3.2 Get the API key (YOU)
1.	Create a Gemini API key in Google AI Studio.
2.	Paste it only into your local .env. Never into the chat, the PRD, or any committed file.
3.	If the key ever leaks, delete it and create a new one immediately.
3.3 Read the official Live API docs and write down these facts (YOU, VERIFY)
Fill this table in. Keep it in a file called docs/VERIFIED_FACTS.md so the agent can read it too.
Fact	Your finding	Date checked
Current Live model id (native audio)		
Supports Telugu? Hindi? English?		
Input audio format (expected PCM16, mono, 16 kHz)		
Output audio format (expected PCM 24 kHz)		
Function calling supported on this model?		
Input and output transcription supported?		
Max session duration (audio only)		
Connection lifetime and go-away behaviour		
Session resumption supported? How?		
Free-tier quota (requests, concurrent sessions, tokens)		
Free-tier data-use terms (are inputs used to improve models?)		
Paid tier needed for demo day?		
Python SDK package name and minimum version		
3.4 Decide on quota and privacy (YOU)
Based on the table above, decide whether demo day uses a paid or higher-limit key. Your consent screen text (FR-01, NFR-23) must honestly say audio is processed by Google's service. If free-tier terms allow model training on inputs, say so or use a paid key.
3.5 Create the repo (YOU)
sih26097/
  docs/PRD.md
  docs/VERIFIED_FACTS.md
  .gitignore        (must contain .env)
  .env              (local only, never committed)
  .env.example      (committed, no real values)
.env contents:
GEMINI_API_KEY=your_key_here
GEMINI_LIVE_MODEL=the_live_model_id_from_docs
GEMINI_TEXT_MODEL=a_text_model_id_for_fallback_calls
APP_ENV=dev
Run git init, make a first commit containing the PRD, .gitignore and .env.example only. Confirm with git status that .env is not tracked.
3.6 Set the agent rules file (YOU)
Open the folder in Antigravity. Check Antigravity's docs for the exact place to store project rules, then add this text:
Read docs/PRD.md and docs/VERIFIED_FACTS.md first, every session. Do only the phase I name. Never hardcode API keys, model names, pathways, diffs, badges or numbers. Read config from environment variables. Never commit .env. Never print or log the API key. Commit after each phase with a clear message. Show verification output (commands run and results). Then stop and wait for my next instruction.
3.7 Step 0 done when
•	☐ VERIFIED_FACTS.md is filled in
•	☐ .env works locally and is git-ignored
•	☐ Rules file is saved in Antigravity
•	☐ Headphones and hotspot are ready

4. Phase 0: Live voice gate (most important step)
Goal: prove the Live model can handle Telugu and Hindi speech and tool calls before you build anything else.
4.1 AGENT prompt
Read docs/PRD.md and docs/VERIFIED_FACTS.md. Do Phase 0 only. Build a bare FastAPI endpoint /ws/live and a plain HTML or React page. Flow: browser mic capture with getUserMedia (echo cancellation on) and an AudioWorklet that downsamples to PCM16 16 kHz, sent over WebSocket to the backend; backend relays to the Gemini Live API; play returned audio at 24 kHz; show live input and output transcripts; show a state indicator (connecting, listening, speaking). Register one dummy tool called ping and display on screen every time it is called. Read the model id and key from env. No database, no engine, no styling work.
4.2 YOU test (about 1 hour)
Do this with headphones on, in a quiet room first, then with noise.
Test	What to try	Record
Telugu	Speak naturally for 2 minutes about studies, work, sewing machine	Transcript accuracy, reply language
Hindi	Same story in Hindi	Same
English	Same story in English	Same
Mixed	Telugu with English words, Hindi with English words	Does it follow the mix?
Other voices	A friend and a family member speak	Accent robustness
Noise	Fan, TV, or street sound in the background	Error rate
Interruption	Talk while the assistant is speaking	Does playback stop (barge-in)?
Tool call	Say something that should trigger ping	Reliable? How often?
Latency	Stop speaking, count seconds until reply	Seconds
Session limit	Keep it running until it cuts off or sends a go-away	Minutes
4.3 Verdict (YOU)
Write one paragraph in docs/GATE0_VERDICT.md: Telugu quality, Hindi quality, tool calling, latency, session limits, decision.
4.4 GATE
Result	Action
Telugu and Hindi acceptable, tool calling works	Proceed to Phase 1
Speech is fine but tool calling is unreliable	Use the PRD fallback: parallel text-extraction call on each finalized user turn
Telugu quality unacceptable	Switch to the pipeline fallback (streaming STT, then LLM, then TTS) behind the same WebSocket protocol. Tell the agent to redo Phase 0 on that basis
Do not continue until this is settled. Commit the working Phase 0 code.

5. Phase 1: Skeleton
Goal: project structure, database, seeded tables, empty UI shell.
5.1 YOU: start the data work now (slowest task)
This runs in parallel with every phase. Do not let the agent invent any of it.
A. Pick the demo geography. One district and 3 to 4 blocks. Write them down.
B. NSQF qualifications: 10 to 12 rows. Use official sources only (NCVET, Skill India, NSDC listings). Never invent qualification codes.
Column	Notes
trade	e.g. tailoring, catering, electrician, etc.
qualification_name	Exactly as in the official listing
nsqf_level	Number
entry_education	none, primary, 8th, 10th, 12th, ITI, graduate
duration_months	From the listing
sector	Sector skill council name
self_employment_suitable	true or false (your judgement, noted)
requires_travel	true or false
equipment_needed	e.g. sewing machine
route_type	self, wage, or both
source_url	The page you read it from
source_note	What you checked
last_verified	Date
is_sample	Keep true until you have verified the row
Choose trades so your two personas work: tailoring (persona A) and catering or hospitality (persona B), plus 8 to 10 others across agriculture, food processing, electrical, retail and so on. Include at least one trade that needs travel and one that needs a long duration, so what-if has something to exclude.
C. Skill adjacency table: 15 to 20 rows. Format: from_skill, to_trade, closeness (direct/adjacent). Example idea: tailoring to embroidery is adjacent. Write these from your own knowledge and ask a domain person to review if you can.
D. Sample training centres. Name, block, trade, seats, next batch date, mode. Mark all is_sample=true.
E. Sample opportunities. Trade, type (wage, self, order), block, note, verified flag. Leave some trades with no opportunity on purpose so the honest fallback demo works.
Save all of these as CSV files. The agent will seed from them.
5.2 AGENT prompt
Read docs/PRD.md. Do Phase 1 only. Create the repo structure from section 14. FastAPI app with GET /api/health. SQLite database with all tables from section 8 (no caste, community, religion, address or ID fields anywhere). A seed script that loads CSVs from backend/data/. Create placeholder CSVs with 10 to 12 NSQF rows where source_note is TODO verify and is_sample is true; I will replace them with real data. React + Vite + Tailwind shell with React Router routes for Consent, Live and Official, and a footer on every screen reading: NSQF = verified subset | centres, opportunities, demand = sample data. Keep the Phase 0 code working. Do not build the engine.
5.3 YOU verify
•	☐ curl http://localhost:8000/api/health returns OK
•	☐ Database file exists and tables are seeded (open with a SQLite viewer)
•	☐ npm run dev shows three routes and the footer
•	☐ .env is not in git status
Commit.
5.4 
`get_pathways`, `set_constraint` and `confirm_profile` are declared `behavior: BLOCKING`. `update_profile` is `NON_BLOCKING` with `scheduling: SILENT`.
6. Phase 2: Engine first (no LLM)
Goal: the deterministic rule engine, fully tested, before any live voice touches it.
6.1 YOU: swap in the real data
Before or during this phase, replace the placeholder NSQF CSV with your verified rows. Keep is_sample=true on any row you have not verified.
6.2 YOU: write the persona test cases (expected results)
The agent writes the tests, but you define what the correct answer is. Write at least 15 cases in plain language first, for example:
#	Persona	Expected behaviour
1	Persona A: 10th pass, sewing machine, home_only, wants own work	Tailoring pathway ranks first
2	Persona B: catering experience, wage, urgent	Catering or hospitality pathway ranks first
3	Primary education only	Higher-entry qualifications excluded with reason
4	Graduate	Nothing excluded for education
5	home_only	Travel-required routes excluded
6	max 3 months	Longer courses excluded with reason like Requires 6 months, your limit is 3
7	work_preference either	Both routes allowed
8	No interests stated	Still returns results, interest factor Unknown
9	No matching trade	Empty state with reasons for every exclusion
10	Trade with no opportunity	Status exactly No verified opportunity found, training pathway still returned
11	Telugu synonym input	Normalizer maps it to the right trade
12	Hindi synonym input (silai)	Same
13	Remove a constraint	Result count never drops
14	Run same input twice	Identical output
15	Every excluded item	Has a human-readable reason
6.3 AGENT prompt
Read docs/PRD.md. Do Phase 2 only. Build schema.py (Pydantic), normalize.py (Telugu, Hindi, English synonym lookup to fixed skill and trade tags), engine_config.yaml (weights and thresholds), engine.py (hard filters FR-30, factor labels FR-31, ranking FR-32, top 3 output FR-33, opportunity honesty FR-34, recompute with diff FR-35, no-result state FR-38). The engine must be pure Python, deterministic, with no network access and no numeric scores in output. Add POST /api/pathways and POST /api/recompute. Write pytest tests for the 15 cases I provide below. [paste your 15 cases]. Show pytest output and sample curl outputs including a diff.
6.4 YOU verify
•	☐ pytest all green
•	☐ Curl /api/pathways with persona A: sensible result
•	☐ Curl /api/recompute with max 3 months: a diff with reasons
•	☐ Grep the code: no hardcoded pathway names or numbers outside config and data
•	☐ Unplug internet: engine still answers
•	☐ Ask a domain reviewer to sanity-check results if reachable
Commit.

7. Phase 3: Live bridge
Goal: production-quality version of Phase 0, with sessions, resumption and barge-in.
Switch the coding model to the strongest available.
7.1 AGENT prompt
Read docs/PRD.md and docs/VERIFIED_FACTS.md. Do Phase 3 only. Turn the Phase 0 relay into live.py: Live session manager with session resumption (keep the latest handle in memory), handling of the go-away notice by reconnecting before close, relay of audio both ways, input and output transcription events, state events (connecting, listening, speaking, thinking, reconnecting, error) per section 9.2. In React: audio folder with AudioWorklet capture, playback queue with barge-in (stop playback when the user speaks), and a voice panel with big mic state and transcript. Add the stop button and the typed-input message type. Use the system instruction from PRD section 5.3 loaded from a file. No tools yet beyond what Phase 0 had. Never write audio to disk. Logs must contain event types and timings only, no transcript text.
7.2 YOU verify
•	☐ A 2-minute live conversation works with streaming transcripts
•	☐ Interrupt the assistant mid-sentence: playback stops
•	☐ Run past the session limit (from your VERIFIED_FACTS): the app reconnects and shows Reconnecting briefly
•	☐ Kill the backend or network mid-session: a clear error and fallback options appear
•	☐ Search the repo and logs: no audio files, no transcript text in logs
Commit.

8. Phase 4: Live profile via tools
Goal: the profile card fills in live as the person speaks.
8.1 AGENT prompt
Read docs/PRD.md. Do Phase 4 only. In tools.py implement the tool declarations from section 5.4 for update_profile and confirm_profile. Validate every argument; reject invalid enum values with a recoverable tool error. Pass skills, interests and current_or_past_work through normalize.py; unknown terms are stored as free text flagged unmapped and never feed ranking. Add the backend blocklist filter for caste, community, religion, address and ID numbers (log only blocked field). Make update_profile idempotent per field (latest wins, history kept in session log) and rate-limited. Push profile_update events to the browser. Build the ProfileCard component with stated (green), inferred (amber) and missing (grey) chips, highlighting missing high-priority fields. Add manual field editing with the edit_log table (PATCH /api/session/{id}/profile). Add the read-back and confirmation flow. Add pytest tests for tool validation, blocklist and normalizer.
8.2 YOU verify (speak persona A in Telugu)
•	☐ Chips appear within a second of each fact
•	☐ Inferred facts show amber and get confirmed by the assistant
•	☐ Say a blocked word (for example a caste name or a fake ID number): it is not shown, not stored, not repeated by the assistant
•	☐ Edit a field by hand: the edit log records old and new value
•	☐ The assistant reads the profile back and confirm_profile fires after you say yes
•	☐ pytest green
Commit.

9. Phase 5: Live pathways and what-if
Goal: the demo's main event. Pathways appear, you change a condition by voice, the diff explains why.
9.1 AGENT prompt
Read docs/PRD.md. Do Phase 5 only. Implement get_pathways and set_constraint tools calling the engine. get_pathways before confirmation must return an unconfirmed preview marker. Tool results are short structured text with pathway names, duration, one-line reasons, opportunity status, and for set_constraint a diff summary, with no scores. Push pathways and diff events to the browser. Build PathwayCard (with sample-data tags on centres and opportunities), WhyDrawer (factor badges with reasons), WhatIfBar (months slider 1 to 12 plus no limit, mobility dropdown, work-preference toggle, time dropdown), DiffBanner (dropped, added, kept with reasons; removed cards animate to a collapsed Excluded because list), removable constraint chips and a Reset button. Add POST /api/explain that only rephrases engine reason strings, falling back to the joined reasons if it fails. The assistant's spoken explanation must use only the returned tool results.
9.2 YOU verify (the honesty tests)
Run each in Telugu, Hindi and English if you can.
Test	Expected
Speak persona A, confirm	2 to 3 pathways within 3 seconds
Say I cannot spend five months	One pathway drops, diff banner shows the reason, assistant explains
Say I cannot travel	Centre-based routes excluded with reason
Remove the constraint with the chip or Reset	Pathways return
Use the UI slider instead of voice	Same result as voice
Tempt the model: What about nursing? or Can you get me a government job?	It does not name anything the engine did not return and does not promise a job
A trade with no opportunity	Shows exactly No verified opportunity found
Any time the model names an unreturned course, tighten the system instruction and retest. Commit once all pass.

10. Phase 6: Official view
Goal: a small, honest dashboard.
10.1 YOU
Decide what the sample story is (for example, demand for tailoring exceeds seats in one block). Keep it believable but clearly labelled.
10.2 AGENT prompt
Read docs/PRD.md. Do Phase 6 only. Write backend/data/generate_sample_profiles.py with a fixed random seed that generates sample_profiles (block, interested_trade, education_level, skills, missing_skills, no personal fields). Build GET /api/official/summary with block and trade filters, all numbers computed by SQL from the database, never hardcoded. Implement small-cell suppression (groups under 5 merge into Other (suppressed)). Build the Official page: bar chart of demand by trade (Recharts), top skill gaps, capacity table (interested profiles vs sample seats, gap, shortfall in red), and a prominent banner reading Sample data (generated for demo). Sessions with the optional consent box ticked are kept separate and labelled differently from generated samples.
10.3 YOU verify
•	☐ Run your own SQL queries: dashboard numbers match
•	☐ Filter to a block with few profiles: suppression appears
•	☐ The sample banner is visible without scrolling
Commit.

11. Phase 7: Fallbacks and polish
Goal: the demo must survive failure.
11.1 YOU: record the cached replays first
Run persona A and persona B live, successfully, once each. You will give the agent the event logs (transcript, tool calls, results) so it can build replays. If the app does not export the log yet, ask the agent to add that in this phase.
11.2 AGENT prompt
Read docs/PRD.md. Do Phase 7 only. Add typed input mode (text turns into the Live session, or to POST /api/extract if the Live session is down). Add cached replay for personas A and B via GET /api/demo/replay/{persona}, replayed through the same UI and clearly labelled Cached demo replay. Add the manual form path. Add clear error states and retry. Do a privacy audit: confirm no audio stored, logs contain no transcript text, no forbidden fields exist in the schema. Check the responsive layout, large touch targets, adjustable text size and the speaking and listening indicator. Write README.md with run instructions and REHEARSAL.md with the demo checklist.
11.3 YOU verify
•	☐ Pull the network cable or turn off Wi-Fi mid-demo: typed mode and replay still work, engine still answers
•	☐ Switch from live to replay in under 30 seconds (success criterion S6)
•	☐ Three full run-throughs of the 2 to 3 minute script, no help from the agent
•	☐ Open the app on a phone-sized window: usable
•	☐ Grep for secrets: nothing in the repo
Commit.

12. Phase 8: Recording day
12.1 YOU
1.	Charge the laptop, pack headphones and the hotspot, copy the project locally.
2.	Run the demo script from PRD section 15 twice in a row. Both must pass S1 to S6.
3.	Record a backup video of a full successful run (screen plus audio).
4.	Record your measured numbers: profile fields correct out of total across your 10 to 15 test conversations (PRD 11.3). Put them on one slide. Do not claim a headline accuracy percentage.
5.	Prepare the real-vs-sample data slide.
6.	Update the architecture diagram (PRD section 18): live WebSocket path, tool-calling loop to the rule engine, WhatsApp marked Planned, IVR marked Planned, facilitator mode box, and an honest note that live speech needs internet.
12.2 Backup order if something fails live
Typed input, then cached replay, then recorded video. Announce the switch calmly and keep the story going.

13. Voice accuracy evaluation (do alongside Phases 4 and 5)
Record 10 to 15 short conversations: Telugu, Hindi and mixed, with different speakers and some noise. Use a sheet like this:
Conversation	Language	Speaker	Noise	Fields correct	Fields wrong	Fields missed	Re-asks
1							
Total the columns and present them as simple counts, for example 42 of 50 fields correct.

14. When the agent goes wrong
Symptom	What to do
Agent changes many unrelated files	Revert with git, restate: only touch files for this phase
Agent hardcodes a pathway, number or model id	Reject. Point to rule 4 and ask for a fix reading from config or data
Agent claims it works without showing output	Ask for the exact commands and outputs, then run them yourself
Agent asks for your API key in chat	Refuse. Tell it to read from the environment
Same bug after 3 attempts	Switch to the stronger model, paste the exact error and logs, ask for root cause first
Audio is choppy or silent	Check sample rates (16 kHz in, 24 kHz out), AudioWorklet loading, browser mic permission, and that headphones are on
Model speaks about unreturned courses	Tighten the system instruction, confirm tool results are the only source, add the tempting prompt to your test list
Telugu transcripts are poor	Revisit the Gate 0 decision and the pipeline fallback
Quota errors	Check VERIFIED_FACTS, use a paid key for rehearsal and demo day

15. Master checklist
Manual one-time tasks
•	☐ Tools installed, API key obtained, .env created and git-ignored
•	☐ VERIFIED_FACTS.md filled in from official docs
•	☐ Quota and data-use terms checked, paid key decision made
•	☐ Agent rules file saved
•	☐ Gate 0 verdict written
•	☐ Demo district and blocks chosen
•	☐ 10 to 12 NSQF rows compiled with source URLs and verified dates
•	☐ Adjacency table (15 to 20 rows) written
•	☐ Sample centres and opportunities written, some trades intentionally empty
•	☐ 15 expected persona cases written
•	☐ Voice accuracy sheet completed
•	☐ Cached replays recorded
•	☐ Backup video recorded
•	☐ SIH portal fields, page limit and team details confirmed
•	☐ Domain reviewer asked to check rules and adjacency, if reachable
Final acceptance (from PRD 11.4)
•	☐ S1 to S6 met on two consecutive full runs
•	☐ No hardcoded pathway, diff, badge or number anywhere
•	☐ Sample tags on every relevant screen
•	☐ No audio stored, logs clean
•	☐ Fallback tested by unplugging the network mid-demo
•	☐ Recorded backup video done

16. Things I could not confirm
•	Whether a coding model called Gemini 3.8 Flash exists. Use what your Antigravity dropdown shows.
•	The current Live model id, language support, limits, quotas and pricing. Read Google's official docs and record them in VERIFIED_FACTS.md.
•	Antigravity's exact location for project rules. Check its documentation.
•	The SIH presentation template and page limit. Check the official portal.
