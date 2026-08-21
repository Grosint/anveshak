# Eager PDF Generation on Shared Docker Volume

## Pattern
Generate PDF eagerly at report creation time in the worker, store on a shared Docker volume, let the API serve the cached file. Don't use a separate ARQ job for PDF generation.

## Why
A separate `generate_report_pdf` ARQ job creates a dead-code trap: the API enqueues a job name that doesn't exist in the worker's `functions` list. The job silently disappears into Redis with no error. PDF downloads return 202 forever.

## Implementation
1. Worker's `generate_report()` adds step 11 after storing the report:
   ```python
   pdf_path = await generate_pdf(report_id, pdf_data, s.pdf_output_dir)
   await conn.execute("UPDATE reports SET pdf_path = $1 WHERE id = $2", pdf_path, report_id)
   ```
2. PDF generation is wrapped in try/except — failure is non-fatal (report content still stored)
3. API endpoint checks `pdf_path` column + `os.path.exists()` → serves FileResponse
4. Shared volume: `reporter_output` mounted at `/app/reports` in both `report-worker` and `api` containers

## Pitfall: env var name mismatch
Compose sets `REPORT_OUTPUT_DIR=/app/reports` but settings.py read `pdf_output_dir` defaulting to `/tmp/anveshak/reports`. PDF written to wrong path — visible in worker container but not API container. Fix: settings.py reads `REPORT_OUTPUT_DIR` and aliases to `pdf_output_dir`.

## Pitfall: datetime not subscriptable
Jinja2 template does `sig.get('created_at')[:10]` but asyncpg returns `datetime` objects, not strings. Fix: use `|string` filter before slicing: `{{ (sig.get('created_at', '')|string)[:10] }}`.
