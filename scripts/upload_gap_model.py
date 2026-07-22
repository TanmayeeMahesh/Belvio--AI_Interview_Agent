"""
One-time upload of the fine-tuned Flan-T5 gap-question model to a PRIVATE Hugging Face model repo.

The ~990 MB weights are NOT committed to git. The app downloads them at boot from this repo
(set GAP_MODEL_REPO + HF_TOKEN in the deployment env — see docs/INTEGRATION_PLAN.md).
Run this ONCE from a machine that has the local model dir and is logged in to Hugging Face.

Usage:
    pip install huggingface_hub
    huggingface-cli login                 # or: export HF_TOKEN=hf_xxx
    python scripts/upload_gap_model.py --repo tanmayee2025/belvio-gap-flan-t5
"""
import argparse
import os
import sys

LOCAL_DIR = "flan_t5_finetuned_frozen_encoder_local_save"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True,
                    help="target repo id, e.g. tanmayee2025/belvio-gap-flan-t5")
    ap.add_argument("--local-dir", default=LOCAL_DIR)
    ap.add_argument("--public", action="store_true",
                    help="make the repo public (default: private)")
    args = ap.parse_args()

    if not os.path.isdir(args.local_dir):
        sys.exit(f"Local model dir not found: {args.local_dir}")

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        sys.exit("huggingface_hub not installed. Run: pip install huggingface_hub")

    token = os.getenv("HF_TOKEN")  # falls back to the cached CLI login if unset
    api = HfApi(token=token)

    print(f"Creating model repo '{args.repo}' (private={not args.public}) ...")
    create_repo(args.repo, repo_type="model", private=not args.public,
                exist_ok=True, token=token)

    print(f"Uploading '{args.local_dir}' -> '{args.repo}' (~990 MB, may take a while) ...")
    api.upload_folder(
        folder_path=args.local_dir,
        repo_id=args.repo,
        repo_type="model",
        commit_message="Upload fine-tuned Flan-T5 (frozen encoder) gap-question model",
    )
    print("\nDone. Set these in the deployment env (HF Space secrets):")
    print(f"  GAP_MODEL_REPO={args.repo}")
    print("  HF_TOKEN=<a token with READ access to that repo>")


if __name__ == "__main__":
    main()
