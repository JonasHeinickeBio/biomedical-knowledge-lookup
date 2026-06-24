#!/usr/bin/env python3
"""
Test runner for functional adapter tests.

Usage:
    poetry run python tests/functional/run_tests.py [--network] [--api]

Options:
    --network    Include network tests (default)
    --api        Include API key required tests (default: skipped)
    --verbose    Show detailed output
    --help       Show this help message
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))



def main():
    parser = argparse.ArgumentParser(
        description="Run functional adapter tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all network tests
    poetry run python tests/functional/run_tests.py --network

    # Run tests with API key support
    poetry run python tests/functional/run_tests.py --api

    # Run specific tests
    poetry run pytest -m functional -m network tests/functional/test_api_responses.py::test_uniprot_search
        """
    )

    parser.add_argument(
        "--network",
        action="store_true",
        default=True,
        help="Include network tests (default)"
    )
    parser.add_argument(
        "--api",
        action="store_true",
        default=False,
        help="Include API key required tests"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Show detailed output"
    )
    parser.add_argument(
        "--pytest-args",
        type=str,
        default="",
        help="Additional arguments to pass to pytest"
    )

    args = parser.parse_args()

    # Build pytest command
    pytest_args = ["-m", "functional"]

    if args.network:
        pytest_args.extend(["-m", "network"])

    if not args.api:
        pytest_args.extend(["-m", "not api"])

    if args.verbose:
        pytest_args.append("-v")

    # Add any additional pytest arguments
    if args.pytest_args:
        pytest_args.extend(args.pytest_args.split())

    # Run pytest using poetry to ensure correct environment
    cmd = ["poetry", "run", "pytest"] + pytest_args
    print(f"Running functional adapter tests: {' '.join(cmd)}")
    print("=" * 70)

    result = subprocess.run(cmd)
    return_code = result.returncode

    # Print summary
    print("\n" + "=" * 70)
    print("FUNCTIONAL TEST SUMMARY")
    print("=" * 70)

    if return_code == 0:
        print("\n✓ All functional tests passed!")
    else:
        print(f"\n✗ Tests failed with exit code {return_code}")
        print("\nTip: Run with --api flag to test adapters requiring API keys")
        print("   Set API keys in environment variables:")
        print("   - BIOPORTAL_API_KEY")
        print("   - UMLS_API_KEY")
        print("   - DISGENET_API_KEY")
        print("   - DRUGBANK_API_KEY")
        print("\n   Note: OpenTargets and ChEMBL no longer require API keys")

    return return_code


if __name__ == "__main__":
    sys.exit(main())
