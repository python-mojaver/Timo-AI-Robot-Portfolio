"""Compare identical audio bytes with configured vs empty STT prompt.

Run as a separate process; does not change .env or the running server.
No extra packages beyond the project's existing python-dotenv are required.
"""
import argparse
import csv
from datetime import datetime
import hashlib
from pathlib import Path
import re
import time


def normalize(text):
    text = (text or "").replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    text = text.replace("\u200c", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


def distance(reference, hypothesis):
    row = list(range(len(hypothesis) + 1))
    for i, left in enumerate(reference, 1):
        new = [i]
        for j, right in enumerate(hypothesis, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j - 1] + (left != right)))
        row = new
    return row[-1]


def scores(reference, hypothesis):
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        raise ValueError("Reference text is empty after normalization.")
    word_errors = distance(ref.split(), hyp.split())
    char_errors = distance(ref, hyp)
    return {"word_errors": word_errors, "ref_words": len(ref.split()),
            "char_errors": char_errors, "ref_chars": len(ref),
            "wer": word_errors / len(ref.split()), "cer": char_errors / len(ref)}


def cases_from_args(args):
    paths = [args.audio] if args.audio else sorted(args.cases.glob("*.wav"))
    if not paths:
        raise ValueError("No WAV files found.")
    if args.reference and not args.audio:
        raise ValueError("--reference is only for --audio; in --cases mode use matching .txt files.")
    cases = []
    for path in paths:
        ref_path = args.reference or path.with_suffix(".txt")
        reference = ref_path.read_text(encoding="utf-8-sig") if ref_path.exists() else None
        if args.cases and reference is None:
            raise ValueError("Missing reference: " + str(ref_path))
        if args.reference and reference is None:
            raise ValueError("Reference does not exist: " + str(ref_path))
        if reference is not None:
            scores(reference, reference)
        cases.append((path, path.read_bytes(), reference))
    return cases


def run(args, stt):
    cases = cases_from_args(args)
    models = [stt.GROQ_MODEL]
    if args.include_turbo and "whisper-large-v3-turbo" not in models:
        models.append("whisper-large-v3-turbo")
    prompts = [("configured", stt.PERSIAN_PROMPT), ("empty", "")]
    if not stt.PERSIAN_PROMPT.strip():
        print("NOTE: configured prompt is already empty; these two prompt conditions are identical.")
    original = stt.GROQ_MODEL, stt.PERSIAN_PROMPT
    columns = ["file", "sha256", "bytes", "model", "prompt", "prompt_sha256", "rep",
               "status", "latency_ms", "reference", "returned_text", "normalized_text",
               "word_errors", "ref_words", "char_errors", "ref_chars", "wer", "cer", "error"]
    rows, first = [], True
    # Exclusive creation protects previous measurements. Flush every request.
    with args.output.open("x", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        handle.flush()
        try:
            for path, data, reference in cases:
                for model in models:
                    for label, prompt in prompts:
                        for rep in range(1, args.repeat + 1):
                            if not first and args.delay:
                                time.sleep(args.delay)
                            first = False
                            stt.GROQ_MODEL, stt.PERSIAN_PROMPT = model, prompt
                            row = dict(file=path.name, sha256=hashlib.sha256(data).hexdigest(),
                                       bytes=len(data), model=model, prompt=label,
                                       prompt_sha256=hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest(),
                                       rep=rep, reference=reference if reference is not None else "")
                            started = time.perf_counter()
                            try:
                                text = stt._groq_transcribe(data) or ""
                                row.update(status="ok", returned_text=text, normalized_text=normalize(text))
                                if reference is not None:
                                    row.update(scores(reference, text))
                            except stt.STTError as exc:
                                row.update(status="error", error=str(exc))
                            except Exception as exc:
                                row.update(status="error", error=type(exc).__name__)
                            row["latency_ms"] = round((time.perf_counter() - started) * 1000)
                            writer.writerow(row)
                            handle.flush()
                            rows.append(row)
                            print(f"{path.name} {model} prompt={label} {row['status']} {row['latency_ms']}ms")
        finally:
            stt.GROQ_MODEL, stt.PERSIAN_PROMPT = original
    print("Results: " + str(args.output.resolve()))
    for model in models:
        for label, _ in prompts:
            group = [r for r in rows if r["model"] == model and r["prompt"] == label]
            valid = [r for r in group if r["status"] == "ok" and "wer" in r]
            failures = sum(r["status"] == "error" for r in group)
            print(f"{model} prompt={label} errors={failures}/{len(group)} scored={len(valid)}")
            if valid:
                corpus_wer = sum(r["word_errors"] for r in valid) / sum(r["ref_words"] for r in valid)
                corpus_cer = sum(r["char_errors"] for r in valid) / sum(r["ref_chars"] for r in valid)
                macro_wer = sum(r["wer"] for r in valid) / len(valid)
                print(f"  corpus_WER={corpus_wer:.4f} corpus_CER={corpus_cer:.4f} macro_WER={macro_wer:.4f}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio", type=Path)
    source.add_argument("--cases", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--include-turbo", action="store_true")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--delay", type=float, default=4.0)
    parser.add_argument("--output", type=Path,
                        default=Path("stt_results_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"))
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10 or not 0 <= args.delay <= 60:
        parser.error("Use repeat=1..10 and delay=0..60.")
    import speech_to_text as stt
    try:
        rows = run(args, stt)
    except (ValueError, OSError) as exc:
        parser.exit(1, "ERROR: " + str(exc) + "\n")
    return 1 if any(row["status"] == "error" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
