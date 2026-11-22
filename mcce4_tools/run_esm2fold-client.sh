#!/usr/bin/env bash
# Fold a supplied results directory, or the current working directory.
set -eo pipefail

dry_run=
redo=false
force_batch=false
results_directory=
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry_run=--dry-run ;;
        --redo) redo=true ;;
        --batch) force_batch=true ;;
        -h|--help)
            echo "Usage: $0 [RESULTS_DIR] [--dry-run] [--redo] [--batch]"
            echo "  RESULTS_DIR  Directory containing seqNN/protein.fasta (default: current directory)."
            echo "  --dry-run  Validate inputs without API requests."
            echo "  --redo     Rerun into fresh esmfold2-client_results directories."
            echo "  --batch    Use Biohub Batch for every sequence (default: Batch above 768 residues)."
            echo "Limits are advisory; larger sequences are sent intact for Biohub to decide."
            echo "Outputs: seqNN/esmfold2-client_results (reruns: esmfold2-client_results_2, etc.)."
            exit 0
            ;;
        -*) echo "Unknown option: $arg. Use --help for usage." >&2; exit 2 ;;
        *)
            if [[ -n $results_directory ]]; then
                echo "Supply only one results directory. Use --help for usage." >&2
                exit 2
            fi
            results_directory=$arg
            ;;
    esac
done
cd -- "${results_directory:-.}"
echo "Results directory: $PWD"

if [[ ${CONDA_DEFAULT_ENV:-} != esmfold2-client ]]; then
    if command -v conda >/dev/null 2>&1; then
        conda_base=$(conda info --base)
    else
        conda_base="$HOME/miniconda3"
    fi
    if [[ ! -f "$conda_base/etc/profile.d/conda.sh" ]]; then
        echo "Cannot find Conda initialization script." >&2
        exit 1
    fi
    source "$conda_base/etc/profile.d/conda.sh"
    conda activate esmfold2-client
fi
command -v esmfold2-client >/dev/null

shopt -s nullglob
inputs=(seq[0-9]*/protein.fasta)
if (( ${#inputs[@]} == 0 )); then
    echo "No seq*/protein.fasta inputs found." >&2
    exit 1
fi
completed=0
skipped=0
failed=0
for fasta in "${inputs[@]}"; do
    directory=${fasta%/protein.fasta}
    length=$(python - "$fasta" <<'PY'
import sys
from pathlib import Path
from esmfold2_local.inputs import load_fasta, validate_spec
spec = validate_spec(load_fasta(Path(sys.argv[1])))
if len(spec['sequences']) != 1:
    raise SystemExit('Expected exactly one protein per FASTA')
print(len(spec['sequences'][0]['sequence']))
PY
    )
    mode=()
    mode_name='Sync with client Batch fallback'
    if (( length > 768 )) || [[ $force_batch == true ]]; then
        mode=(--batch)
        mode_name=Batch
    fi
    if (( length > 4096 )); then
        echo "$directory: warning: $length residues exceeds the advisory Batch reference of 4096; Biohub decides acceptance."
    fi
    if [[ $dry_run == --dry-run ]]; then
        esmfold2-client --fasta "$fasta" --pae "${mode[@]}" --dry-run >/dev/null
        echo "$directory: validated ($length residues; $mode_name; no API request)"
        continue
    fi
    existing_complete=false
    complete_directory=
    pending_jobs=()
    # Recognize older output names so existing predictions/jobs are preserved.
    for prior in "$directory"/esmfold2-client_results "$directory"/esmfold2-client_results_[0-9]* \
                 "$directory"/prediction "$directory"/prediction_[0-9]*; do
        if [[ -s "$prior/structure.pdb" && -s "$prior/structure.cif" &&
              -s "$prior/confidence.json" && -s "$prior/request.json" ]]; then
            existing_complete=true
            complete_directory=$prior
        else
            for job in "$prior"/batch-job-*.json; do
                pending_jobs+=("$job")
            done
        fi
    done
    if [[ $existing_complete == true && $redo == false ]]; then
        echo "$directory: already complete in $complete_directory; skipped"
        skipped=$((skipped + 1))
        continue
    fi
    if (( ${#pending_jobs[@]} > 0 )); then
        echo "$directory: incomplete Batch checkpoint found; no new submission, including with --redo." >&2
        echo "Recover an accepted job with the command below. If no handle was returned, check Biohub job state before resubmitting." >&2
        for job in "${pending_jobs[@]}"; do
            printf '  esmfold2-client --resume-batch %q\n' "$PWD/$job" >&2
        done
        failed=$((failed + 1))
        continue
    fi
    output="$directory/esmfold2-client_results"
    attempt=2
    while [[ -e $output ]]; do
        output="$directory/esmfold2-client_results_$attempt"
        attempt=$((attempt + 1))
    done
    echo "$directory: folding $length residues via $mode_name into $output"
    if esmfold2-client --fasta "$fasta" --pae "${mode[@]}" --out "$output"; then
        completed=$((completed + 1))
    else
        echo "$directory: failed; continuing with the next sequence" >&2
        failed=$((failed + 1))
    fi
done
echo "Finished: $completed folded, $skipped skipped, $failed failed."
(( failed == 0 ))
