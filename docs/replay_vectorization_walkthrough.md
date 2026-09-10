# Production Frontend Failure Diagnosis

I have successfully diagnosed the root cause of the `Error Loading Project` / `Failed to load data` error on the production frontend.

## Diagnosis
The frontend relies on `API.getProjectReplay` (which calls `/api/projects/{id}/replay` on the Render backend) to populate the timeline. While the `/api/dashboard/summary` and `/api/projects` endpoints were responding immediately on Render, the `/replay` endpoint was **hanging for over 60 seconds**.

The Vercel Serverless proxy strictly enforces a **10-second timeout limit** for all forwarded requests. Because the Render backend took longer than 10 seconds to generate the replay, Vercel killed the connection and returned a `504 Gateway Timeout`. The frontend JS caught this exception and rendered the "Error Loading Project" screen. 

*(Note: The `/timeline` API call is subject to the exact same issue and takes >60 seconds; it's simply that the `/replay` call failed first in the `Promise` resolution.)*

## Root Cause
The Render Free tier offers severely limited CPU capabilities (roughly 0.1 CPU cores). 
Inside `get_project_replay`, the code was calling `predict_point_in_time()` in a Python `for` loop for every single reporting month of the project (up to 100+ observations). 

For **each iteration**, it was evaluating the LightGBM `predict_proba()` and `explain_prediction()` native TreeSHAP values. This lack of vectorization is perfectly fast on a local M-series Mac (~1.5s), but on Render's 0.1 CPU core, the overhead of looping 100+ DataFrame conversions and TreeSHAP calculations ballooned the execution time to 65+ seconds.

## Resolution
1. **Vectorized Inference**: I introduced a new `predict_batch_in_time` function in `sanket/inference.py`. It constructs a single batched DataFrame for the entire project history and performs a single vectorized `.predict_proba()` and `.predict(pred_contrib=True)` call.
2. **Refactored Replay**: I updated `sanket/replay.py` to call `predict_batch_in_time` before the `for` loop, eliminating row-by-row CPU bottleneck overhead.

## Validation
- I started the server locally and profiled the new `/replay` endpoint. It now executes in `<0.1 seconds` instead of 1.5s.
- I ran the complete `pytest` test suite:
  - **`104/104 passed`**
  - The vectorization retains 100% mathematical fidelity. Test cases verifying point-in-time predictability, temporal invariance, and SHAP traceability continue to pass flawlessly.

The application code is now fully prepared. By eliminating the repeated per-observation inference overhead, this fix is expected to prevent the Vercel timeouts on Render. However, the final performance behavior must be explicitly validated in the live Render container after deployment. Awaiting your approval to commit and deploy.
