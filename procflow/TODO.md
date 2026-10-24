# TODO

## Project overview and navigation — complete
- Explain the problem the project addresses and what it demonstrates.
- Present the complete workflow as a visual, connected pipeline: Container workload → CPU and memory monitoring → Threshold detection → Migration trigger → CRIU checkpoint → Destination restore with runc → Workload continuity verified.
- Distinguish which steps are implemented, simulated, or unavailable based on repository evidence.
- Link each stage to a concise explanation of the relevant project component or script.
- Provide clear navigation between the overview, demo, architecture, workloads, evidence, and setup.
- Use a professional technical theme inspired by the reference: deep navy background, layered blue surfaces, subtle gradients, thin blue borders, white headings with muted blue-gray supporting text, restrained cyan, amber, and teal accents, clean sans-serif typography, consistent spacing, clear hierarchy, simple line icons, and purposeful motion. Make it a refined product and project showcase, not only an admin dashboard.
- Keep the interface responsive and accessible, including sufficient contrast, semantic structure, and keyboard focus.

## Guided end-to-end demo — complete
- Provide a guided demonstration that lets the visitor start or reset the demo when supported.
- Show the workload and a visible counter or other continuity signal before and after migration.
- Display CPU and memory readings, the configured CPU threshold, and sampling interval when available.
- When CPU crosses the threshold, visibly advance through detection, migration trigger, checkpoint, restore, and continuity verification.
- Show step-by-step progress, timestamps or elapsed time, and clear success or failure feedback.
- If the real project cannot be controlled from the browser, create an explicitly labeled simulation using project-consistent demo data. Never present simulated events as real system activity.
- Do not add fake controls that imply real system actions; label a guided simulation “Simulation” throughout and explain how it differs from running the real prototype.

## Architecture and components — complete
- Explain how the repository’s actual components fit together, including the controller, monitoring logic, migration process, CRIU, runc, and workload.
- Use a readable architecture diagram or component map based on the code and documentation.
- For each component, explain its role and link to relevant repository files or scripts where practical.
- Clearly identify external prerequisites and runtime assumptions found in the repo.

## Workloads and monitoring — complete
- Show the actual workload examples provided by the project.
- Explain how CPU and memory are measured and how the threshold decision is made.
- Use real project data if available; otherwise show a clearly marked sample/demo state.
- Include meaningful empty, unavailable, loading, and error states.

## Migration history and evidence — complete
- Present the stages and outcome of each demonstration or migration attempt.
- Surface repository-provided logs, evidence, or test results where appropriate.
- Explain what each result proves, especially whether the workload continued after restore.
- Do not imply production readiness or broader guarantees than the project demonstrates.

## Setup and run guide — complete
- Show the actual commands and prerequisites from the repository documentation.
- Organize setup into understandable steps and explain what users should expect at each step.
- Make commands easy to copy.
- Do not fabricate commands or dependencies.

## Repository-grounded implementation — complete
- Inspect the repository structure, README, source code, scripts, configuration, workloads, logs, and demo before implementation.
- Build on the existing stack and project behavior. Do not invent backend endpoints, claim unsupported capabilities, or replace working project logic with unrelated functionality. If a real integration is unavailable, provide an explicitly labeled demo mode that illustrates the actual project flow.
- Follow the repository’s existing framework, conventions, and package manager. Reuse existing code, scripts, workload definitions, logs, and documented behavior. Verify every capability statement against the repository.
- Keep the experience polished, responsive, and accessible; use reusable components and handle loading, empty, error, success, and unsupported-feature states.
- Summarize what is implemented, how the demo gets its data, and which parts are simulated or unavailable.
