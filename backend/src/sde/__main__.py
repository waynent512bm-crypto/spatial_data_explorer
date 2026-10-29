"""Command line entry point.

    python -m sde serve --h5ad PATH [--platform xenium] [--layer NAME] [--port 8000]
    python -m sde demo [--out data/demo]
"""

from __future__ import annotations

import argparse
from pathlib import Path

PLATFORMS = ("xenium", "merscope", "cosmx", "unknown")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sde", description="Spatial Data Explorer backend")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="serve an annotated .h5ad")
    serve.add_argument("--h5ad", required=True, type=Path)
    serve.add_argument("--platform", choices=PLATFORMS, default="unknown")
    serve.add_argument("--layer", default=None,
                       help="log-normalized expression layer (default: X)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    demo = sub.add_parser("demo", help="write a small synthetic Xenium-like dataset")
    demo.add_argument("--out", type=Path, default=Path("data/demo"))
    demo.add_argument("--n-cells", type=int, default=20_000)

    args = parser.parse_args(argv)

    if args.command == "demo":
        from .demo import write_demo
        h5ad, boundaries = write_demo(args.out, n_cells=args.n_cells)
        print(f"wrote {h5ad}\nwrote {boundaries}")
        return

    import uvicorn
    from .api import create_app
    from .dataset import Dataset

    print(f"loading {args.h5ad} ...")
    dataset = Dataset.from_h5ad(args.h5ad, platform=args.platform, layer=args.layer)
    print(f"{dataset.n_cells:,} cells x {dataset.n_genes:,} genes; "
          f"default color column: {dataset.detection.column} ({dataset.detection.reason})")
    uvicorn.run(create_app(dataset), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
