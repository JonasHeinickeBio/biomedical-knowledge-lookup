"""
UMLS Crosswalk Client

An optimized class for UMLS crosswalk operations with enhanced functionality.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CrosswalkMapping:
    """Represents a single crosswalk mapping between source and target vocabularies."""

    source_code: str
    source_vocabulary: str
    target_code: str | None = None
    target_vocabulary: str | None = None
    target_name: str | None = None
    cui: str | None = None
    confidence: float = 1.0
    mapping_type: str = "exact"
    error_message: str | None = None

    @property
    def is_successful(self) -> bool:
        """Check if the mapping was successful."""
        return self.target_code is not None and self.error_message is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_code": self.source_code,
            "source_vocabulary": self.source_vocabulary,
            "target_code": self.target_code,
            "target_vocabulary": self.target_vocabulary,
            "target_name": self.target_name,
            "cui": self.cui,
            "confidence": self.confidence,
            "mapping_type": self.mapping_type,
            "error_message": self.error_message,
            "is_successful": self.is_successful,
        }


@dataclass
class CrosswalkResult:
    """Results from a crosswalk operation."""

    source_vocabulary: str
    target_vocabulary: str
    mappings: list[CrosswalkMapping] = field(default_factory=list)
    total_processed: int = 0
    successful_mappings: int = 0
    failed_mappings: int = 0
    execution_time: float = 0.0
    errors: list[str] = field(default_factory=list)

    def add_mapping(self, mapping: CrosswalkMapping):
        """Add a mapping to the result."""
        self.mappings.append(mapping)
        self.total_processed += 1

        if mapping.is_successful:
            self.successful_mappings += 1
        else:
            self.failed_mappings += 1
            if mapping.error_message:
                self.errors.append(f"{mapping.source_code}: {mapping.error_message}")

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.successful_mappings / self.total_processed) * 100

    def get_successful_mappings(self) -> list[CrosswalkMapping]:
        """Get only successful mappings."""
        return [m for m in self.mappings if m.is_successful]

    def get_failed_mappings(self) -> list[CrosswalkMapping]:
        """Get only failed mappings."""
        return [m for m in self.mappings if not m.is_successful]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert results to pandas DataFrame."""
        return pd.DataFrame([mapping.to_dict() for mapping in self.mappings])


class UMLSCrosswalkClient:
    """
    Enhanced UMLS crosswalk client with async support and advanced features.
    """

    def __init__(
        self,
        api_key: str,
        version: str = "current",
        max_concurrent_requests: int = 10,
        request_delay: float = 0.1,
    ):
        """
        Initialize the crosswalk client.

        Args:
            api_key: UTS API key
            version: UMLS version (default: "current")
            max_concurrent_requests: Maximum concurrent requests
            request_delay: Delay between requests in seconds
        """
        self.api_key = api_key
        self.version = version
        self.base_uri = "https://uts-ws.nlm.nih.gov"
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self.session: aiohttp.ClientSession | None = None
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Rate limiting
        self.last_request_time = 0.0

        # Statistics
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()

    async def initialize_session(self):
        """Initialize the HTTP session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def close_session(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _make_request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make an async HTTP request with rate limiting and error handling."""
        if self.session is None:
            await self.initialize_session()

        async with self.semaphore:
            # Rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.request_delay:
                await asyncio.sleep(self.request_delay - time_since_last_request)

            self.last_request_time = time.time()

            try:
                self.total_requests += 1

                assert self.session is not None, "Session must be initialized"
                session = self.session
                if session is None:
                    raise RuntimeError("Session not initialized. Use async with ...")
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        self.successful_requests += 1
                        return await response.json()
                    else:
                        self.failed_requests += 1
                        error_text = await response.text()
                        raise aiohttp.ClientError(f"HTTP {response.status}: {error_text}")

            except Exception as e:
                self.failed_requests += 1
                logger.error(f"Request failed for {url}: {e}")
                raise

    async def crosswalk_code(
        self, source_code: str, source_vocabulary: str, target_vocabulary: str
    ) -> CrosswalkMapping:
        """
        Crosswalk a single code from source to target vocabulary.

        Args:
            source_code: The code to crosswalk
            source_vocabulary: Source vocabulary (e.g., 'SNOMEDCT_US')
            target_vocabulary: Target vocabulary (e.g., 'MSH')

        Returns:
            CrosswalkMapping object
        """
        mapping = CrosswalkMapping(
            source_code=source_code,
            source_vocabulary=source_vocabulary,
            target_vocabulary=target_vocabulary,
        )

        try:
            # Build the endpoint URL
            endpoint = f"/rest/crosswalk/{self.version}/source/{source_vocabulary}/{source_code}"
            url = self.base_uri + endpoint

            params = {"targetSource": target_vocabulary, "apiKey": self.api_key}

            # Make the request
            response_data = await self._make_request(url, params)

            # Process the response
            if "result" in response_data and len(response_data["result"]) > 0:
                result = response_data["result"][0]
                mapping.target_code = result.get("ui")
                mapping.target_name = result.get("name")
                mapping.cui = result.get("cui")

                # Determine confidence based on mapping type
                if result.get("rootSource") == target_vocabulary:
                    mapping.confidence = 1.0
                    mapping.mapping_type = "exact"
                else:
                    mapping.confidence = 0.8
                    mapping.mapping_type = "approximate"

                logger.debug(f"Successfully mapped {source_code} to {mapping.target_code}")
            else:
                mapping.error_message = (
                    f"No mapping found for {source_code} in {target_vocabulary}"
                )
                logger.warning(mapping.error_message)

        except Exception as e:
            mapping.error_message = str(e)
            logger.error(f"Error mapping {source_code}: {e}")

        return mapping

    async def crosswalk_codes(
        self, source_codes: list[str], source_vocabulary: str, target_vocabulary: str
    ) -> CrosswalkResult:
        """
        Crosswalk multiple codes from source to target vocabulary.

        Args:
            source_codes: List of codes to crosswalk
            source_vocabulary: Source vocabulary
            target_vocabulary: Target vocabulary

        Returns:
            CrosswalkResult object
        """
        start_time = time.time()

        result = CrosswalkResult(
            source_vocabulary=source_vocabulary, target_vocabulary=target_vocabulary
        )

        logger.info(
            f"Starting crosswalk: {len(source_codes)} codes from {source_vocabulary} to {target_vocabulary}"
        )

        # Process codes concurrently
        tasks = [
            self.crosswalk_code(code, source_vocabulary, target_vocabulary)
            for code in source_codes
        ]

        # Execute with progress tracking
        for i, task in enumerate(asyncio.as_completed(tasks)):
            try:
                mapping = await task
                result.add_mapping(mapping)

                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(source_codes)} codes")

            except Exception as e:
                logger.error(f"Task failed: {e}")
                # Create a failed mapping
                failed_mapping = CrosswalkMapping(
                    source_code="unknown",
                    source_vocabulary=source_vocabulary,
                    target_vocabulary=target_vocabulary,
                    error_message=str(e),
                )
                result.add_mapping(failed_mapping)

        result.execution_time = time.time() - start_time

        logger.info(
            f"Crosswalk completed: {result.successful_mappings}/{result.total_processed} successful "
            f"({result.success_rate:.1f}%) in {result.execution_time:.2f}s"
        )

        return result

    async def crosswalk_from_file(
        self, input_file: str | Path, source_vocabulary: str, target_vocabulary: str
    ) -> CrosswalkResult:
        """
        Crosswalk codes from a file.

        Args:
            input_file: Path to input file (one code per line)
            source_vocabulary: Source vocabulary
            target_vocabulary: Target vocabulary

        Returns:
            CrosswalkResult object
        """
        input_path = Path(input_file)

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        # Read codes from file
        codes = []
        with open(input_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.isspace():
                    codes.append(line)

        logger.info(f"Read {len(codes)} codes from {input_file}")

        return await self.crosswalk_codes(codes, source_vocabulary, target_vocabulary)

    def save_result(
        self, result: CrosswalkResult, output_file: str | Path, format: str = "txt"
    ) -> None:
        """
        Save crosswalk results to file.

        Args:
            result: CrosswalkResult object
            output_file: Output file path
            format: Output format ('txt', 'json', 'csv', 'excel')
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "txt":
            self._save_txt(result, output_path)
        elif format.lower() == "json":
            self._save_json(result, output_path)
        elif format.lower() == "csv":
            self._save_csv(result, output_path)
        elif format.lower() == "excel":
            self._save_excel(result, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Results saved to {output_file}")

    def _save_txt(self, result: CrosswalkResult, output_path: Path):
        """Save results in text format."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("UMLS Crosswalk Results\n")
            f.write(f"Source Vocabulary: {result.source_vocabulary}\n")
            f.write(f"Target Vocabulary: {result.target_vocabulary}\n")
            f.write(f"Total Processed: {result.total_processed}\n")
            f.write(f"Successful: {result.successful_mappings} ({result.success_rate:.1f}%)\n")
            f.write(f"Failed: {result.failed_mappings}\n")
            f.write(f"Execution Time: {result.execution_time:.2f}s\n")
            f.write(f"{'='*60}\n\n")

            for mapping in result.mappings:
                if mapping.is_successful:
                    f.write(
                        f"{result.source_vocabulary} Code: {mapping.source_code}\t"
                        f"{result.target_vocabulary} Code: {mapping.target_code} - "
                        f"{mapping.target_name}\n"
                    )
                    if mapping.cui:
                        f.write(f"CUI: {mapping.cui}\n")
                    f.write(f"Confidence: {mapping.confidence:.2f}\n\n")
                else:
                    f.write(
                        f"{result.source_vocabulary} Code: {mapping.source_code}\t"
                        f"ERROR: {mapping.error_message}\n\n"
                    )

    def _save_json(self, result: CrosswalkResult, output_path: Path):
        """Save results in JSON format."""
        data: dict[str, Any] = {
            "metadata": {
                "source_vocabulary": result.source_vocabulary,
                "target_vocabulary": result.target_vocabulary,
                "total_processed": result.total_processed,
                "successful_mappings": result.successful_mappings,
                "failed_mappings": result.failed_mappings,
                "success_rate": result.success_rate,
                "execution_time": result.execution_time,
            },
            "mappings": [mapping.to_dict() for mapping in result.mappings],
            "errors": result.errors,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_csv(self, result: CrosswalkResult, output_path: Path):
        """Save results in CSV format."""
        df = result.to_dataframe()
        df.to_csv(output_path, index=False, encoding="utf-8")

    def _save_excel(self, result: CrosswalkResult, output_path: Path):
        """Save results in Excel format."""
        df = result.to_dataframe()

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Mappings", index=False)

            # Add summary sheet
            summary_data: dict[str, Any] = {
                "Metric": [
                    "Source Vocabulary",
                    "Target Vocabulary",
                    "Total Processed",
                    "Successful Mappings",
                    "Failed Mappings",
                    "Success Rate (%)",
                    "Execution Time (s)",
                ],
                "Value": [
                    result.source_vocabulary,
                    result.target_vocabulary,
                    result.total_processed,
                    result.successful_mappings,
                    result.failed_mappings,
                    f"{result.success_rate:.1f}",
                    f"{result.execution_time:.2f}",
                ],
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name="Summary", index=False)

    async def batch_crosswalk(
        self, mappings: list[tuple[str, str]], source_codes: list[str]
    ) -> dict[str, CrosswalkResult]:
        """
        Perform multiple crosswalk operations in batch.

        Args:
            mappings: List of (source_vocab, target_vocab) tuples
            source_codes: List of source codes

        Returns:
            Dictionary of mapping_key -> CrosswalkResult
        """
        results = {}

        for source_vocab, target_vocab in mappings:
            mapping_key = f"{source_vocab}_to_{target_vocab}"
            logger.info(f"Starting batch crosswalk: {mapping_key}")

            result = await self.crosswalk_codes(source_codes, source_vocab, target_vocab)
            results[mapping_key] = result

        return results

    def get_statistics(self) -> dict[str, Any]:
        """Get client statistics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (self.successful_requests / max(self.total_requests, 1)) * 100,
            "version": self.version,
            "max_concurrent_requests": self.max_concurrent_requests,
            "request_delay": self.request_delay,
        }

    def reset_statistics(self):
        """Reset client statistics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0


# Convenience function for simple crosswalk operations
async def crosswalk_codes_simple(
    api_key: str,
    source_codes: list[str],
    source_vocabulary: str,
    target_vocabulary: str,
    version: str = "current",
) -> CrosswalkResult:
    """
    Simple function to crosswalk codes without managing client lifecycle.

    Args:
        api_key: UTS API key
        source_codes: List of codes to crosswalk
        source_vocabulary: Source vocabulary
        target_vocabulary: Target vocabulary
        version: UMLS version

    Returns:
        CrosswalkResult object
    """
    async with UMLSCrosswalkClient(api_key, version) as client:
        return await client.crosswalk_codes(source_codes, source_vocabulary, target_vocabulary)


# Example usage
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UMLS Crosswalk Client")
    parser.add_argument("-k", "--apikey", required=True, help="UTS API key")
    parser.add_argument("-s", "--source", required=True, help="Source vocabulary")
    parser.add_argument("-t", "--target", required=True, help="Target vocabulary")
    parser.add_argument("-i", "--input", required=True, help="Input file path")
    parser.add_argument("-o", "--output", required=True, help="Output file path")
    parser.add_argument(
        "-f",
        "--format",
        default="txt",
        choices=["txt", "json", "csv", "excel"],
        help="Output format",
    )
    parser.add_argument("-v", "--version", default="current", help="UMLS version")
    parser.add_argument("--max-concurrent", type=int, default=10, help="Max concurrent requests")
    parser.add_argument("--delay", type=float, default=0.1, help="Request delay in seconds")

    args = parser.parse_args()

    async def main():
        async with UMLSCrosswalkClient(
            api_key=args.apikey,
            version=args.version,
            max_concurrent_requests=args.max_concurrent,
            request_delay=args.delay,
        ) as client:

            # Perform crosswalk
            result = await client.crosswalk_from_file(
                input_file=args.input, source_vocabulary=args.source, target_vocabulary=args.target
            )

            # Save results
            client.save_result(result, args.output, args.format)

            # Print statistics
            stats = client.get_statistics()
            print("\nClient Statistics:")
            print(f"Total Requests: {stats['total_requests']}")
            print(f"Success Rate: {stats['success_rate']:.1f}%")
            print(f"Crosswalk Success Rate: {result.success_rate:.1f}%")

    asyncio.run(main())
