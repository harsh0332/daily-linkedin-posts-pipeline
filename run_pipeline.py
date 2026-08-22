import os
import sys
import subprocess

def run_step(description, command):
    print(f"\n==================================================")
    print(f"STEP: {description}")
    print(f"COMMAND: {command}")
    print(f"==================================================\n")
    res = subprocess.run(command, shell=True)
    if res.returncode != 0:
        print(f"\n❌ ERROR: Step '{description}' failed with exit code {res.returncode}.")
        sys.exit(res.returncode)

def preflight_gate():
    """Check every pillar's supply before anything is generated.

    2026-08-22: pillars skip silently. The ad pool ran dry and the first
    anyone knew was Monday's post not appearing. preflight.py exits 1 when a
    day would skip, so the run stops here and prints the asks instead of
    finding out afterwards.

      --accept-short   generate anyway, knowing days will be missing
      --refresh        run the fetches that need no input first
    """
    accept_short = "--accept-short" in sys.argv
    refresh = "--refresh" in sys.argv

    cmd = "python3 preflight.py" + (" --refresh" if refresh else "")
    print("\n==================================================")
    print("STEP: 0. Preflight — is every pillar supplied?")
    print(f"COMMAND: {cmd}")
    print("==================================================\n")
    rc = subprocess.run(cmd, shell=True).returncode

    if rc == 0:
        return
    if rc == 2:
        print("\n❌ Preflight could not run (broken config or unreadable file).")
        sys.exit(2)

    if accept_short:
        print("\n⚠️  --accept-short given: generating a short batch knowingly.")
        return

    print("\n" + "=" * 58)
    print("STOPPING BEFORE GENERATION.")
    print("  At least one day would produce nothing. The asks are above.")
    print("")
    print("  Supply what is missing, then run this again. Or:")
    print("    python3 run_pipeline.py --refresh        # fetch what needs no input")
    print("    python3 run_pipeline.py --accept-short   # proceed with a short batch")
    print("=" * 58)
    sys.exit(1)


def main():
    print("🚀 STARTING AUTOMATED LINKEDIN CONTENT PIPELINE...")

    preflight_gate()
    
    # 1. Fetch Fresh Research Data
    run_step("1. Fetching Fresh Reddit RSS & AI News Data", "python3 fetch_reddit_rss.py")
    
    # 2. Dynamic Content Generation & Topic Memory Deduplication
    run_step("2. Generating Fresh Posts & Checking used_topics.json", "python3 generate_all_content.py")
    
    # 3. Copy generated text to standard active file
    run_step("3. Preparing Active Post Files", "cp linkedin_posts_$(date +%Y%m%d).txt linkedin_posts_today.txt 2>/dev/null || true")
    
    # 4. Compile Carousel PDF & PNGs
    run_step("4. Building Dynamic Carousel PDF & Slides", "NODE_PATH=./carousel-routine/node_modules node build_carousel_today.cjs")
    
    # 5. Compile Infographic HTML & PNG
    run_step("5. Building Dynamic Infographic HTML & PNG", "NODE_PATH=./carousel-routine/node_modules node cap_infographic_today.js")
    
    # 6. Send to Slack
    run_step("6. Delivering Fresh Drafts & Assets to Slack", "python3 send_to_slack.py")
    
    # 7. Auto-Schedule to LinkedIn using pipeline_state.json memory
    run_step("7. Auto-Scheduling to LinkedIn (Reading pipeline_state.json)", "NODE_PATH=./carousel-routine/node_modules node schedule_all_posts.cjs")
    
    print("\n==================================================")
    print("🎉 FULL PIPELINE COMPLETED SUCCESSFULLY!")
    print("==================================================\n")

if __name__ == "__main__":
    main()
