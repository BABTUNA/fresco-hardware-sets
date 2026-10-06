# hwsets extract book.pdf [-o out.json] [--spec specs/x.json] [--no-llm]
import argparse, json, sys
from .extract import extract_book


def main():
    ap = argparse.ArgumentParser(prog="hwsets", description="extract door hardware sets from a Division 08 spec PDF")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract", help="extract one PDF to JSON")
    ex.add_argument("pdf")
    ex.add_argument("-o", "--out", help="output file, default stdout")
    ex.add_argument("--spec", help="layout spec to use instead of specs/<book>.json")
    ex.add_argument("--no-llm", action="store_true", help="fail instead of calling the API when no spec exists")
    args = ap.parse_args()
    result = extract_book(args.pdf, spec_path=args.spec, allow_llm=not args.no_llm)
    text = json.dumps(result, indent=1)
    if args.out:
        open(args.out, "w").write(text)
        n = sum(len(s["components"]) for s in result["sets"])
        print(f"{result['file']}: {result['status']}, {len(result['sets'])} sets, {n} components, {len(result['flags'])} flags -> {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
