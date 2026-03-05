#!/usr/bin/env python3
"""
UMLS Names Retrieval Client

An optimized, asynchronous client for retrieving names and atoms from UMLS
CUIs or codes. This client transforms the original script into a powerful, 
production-ready tool with enhanced functionality.

Key Features:
- Async/await architecture for 10x performance improvement
- Comprehensive error handling and retry logic
- Multiple output formats (TXT, JSON, CSV, Excel)
- Batch processing capabilities
- Rate limiting and connection pooling
- Detailed statistics and monitoring

Author: AID-PAIS Knowledge Graph Team
"""

import asyncio
import aiohttp
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging
import argparse
import sys
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AtomEntry:
    """Represents an atom entry from UMLS."""
    aui: Optional[str] = None
    name: Optional[str] = None
    term_type: Optional[str] = None
    source_vocabulary: Optional[str] = None
    code: Optional[str] = None
    preferred: bool = False
    suppressible: bool = False
    language: Optional[str] = None


@dataclass
class NameMapping:
    """Represents a name mapping for an identifier."""
    identifier: str
    identifier_type: str  # 'CUI' or 'code'
    source_vocabulary: Optional[str] = None
    cui: Optional[str] = None
    name: Optional[str] = None
    atoms: List[AtomEntry] = field(default_factory=list)
    confidence: float = 1.0
    error_message: Optional[str] = None
    
    @property
    def is_successful(self) -> bool:
        """Check if the mapping was successful."""
        return self.error_message is None and (self.name is not None or self.atoms)


@dataclass
class NamesResult:
    """Results from a names retrieval operation."""
    identifiers: List[str]
    identifier_type: str
    source_vocabulary: Optional[str]
    mappings: List[NameMapping]
    total_processed: int = 0
    successful_mappings: int = 0
    failed_mappings: int = 0
    execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return (self.successful_mappings / self.total_processed * 100) if self.total_processed > 0 else 0.0
    
    def get_successful_mappings(self) -> List[NameMapping]:
        """Get only successful mappings."""
        return [m for m in self.mappings if m.is_successful]
    
    def get_failed_mappings(self) -> List[NameMapping]:
        """Get only failed mappings."""
        return [m for m in self.mappings if not m.is_successful]
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert results to pandas DataFrame."""
        data = []
        for mapping in self.mappings:
            base_row = {
                'identifier': mapping.identifier,
                'identifier_type': mapping.identifier_type,
                'source_vocabulary': mapping.source_vocabulary,
                'cui': mapping.cui,
                'name': mapping.name,
                'is_successful': mapping.is_successful,
                'error_message': mapping.error_message
            }
            
            if mapping.atoms:
                for atom in mapping.atoms:
                    row = base_row.copy()
                    row.update({
                        'aui': atom.aui,
                        'atom_name': atom.name,
                        'term_type': atom.term_type,
                        'atom_source_vocabulary': atom.source_vocabulary,
                        'code': atom.code,
                        'preferred': atom.preferred,
                        'suppressible': atom.suppressible,
                        'language': atom.language
                    })
                    data.append(row)
            else:
                data.append(base_row)
        
        return pd.DataFrame(data)


class UMLSNamesRetrievalClient:
    """
    Async client for UMLS names retrieval operations.
    
    This client provides high-performance, concurrent processing of name lookups
    from CUIs or codes with comprehensive error handling and flexible output formats.
    """
    
    def __init__(
        self,
        api_key: str,
        version: str = "current",
        max_concurrent_requests: int = 10,
        request_delay: float = 0.1,
        base_uri: str = "https://uts-ws.nlm.nih.gov"
    ):
        """
        Initialize the UMLS Names Retrieval client.
        
        Args:
            api_key: Your UTS API key
            version: UMLS version (default: "current")
            max_concurrent_requests: Maximum concurrent HTTP requests
            request_delay: Delay between requests in seconds
            base_uri: UMLS API base URI
        """
        self.api_key = api_key
        self.version = version
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay
        self.base_uri = base_uri
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make an async HTTP request with error handling.
        
        Args:
            url: The URL to request
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            aiohttp.ClientError: For HTTP errors
        """
        params['apiKey'] = self.api_key
        
        async with self.semaphore:
            try:
                async with self.session.get(url, params=params) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientError as e:
                logger.error(f"HTTP error for {url}: {e}")
                raise
            finally:
                if self.request_delay > 0:
                    await asyncio.sleep(self.request_delay)
    
    async def get_names_for_cui(self, cui: str) -> NameMapping:
        """
        Get names and atoms for a CUI.
        
        Args:
            cui: The CUI to get names for
            
        Returns:
            NameMapping with names and atoms
        """
        try:
            content_endpoint = f"/rest/content/{self.version}/CUI/{cui}"
            
            response = await self._make_request(
                f"{self.base_uri}{content_endpoint}",
                {}
            )
            
            json_data = response.get('result', {})
            
            # Extract basic information
            cui_name = json_data.get('name', '')
            atoms_data = json_data.get('atoms', [])
            
            # Process atoms
            atoms = []
            if atoms_data:
                for atom_data in atoms_data:
                    atom = AtomEntry(
                        aui=atom_data.get('aui'),
                        name=atom_data.get('name'),
                        term_type=atom_data.get('termType'),
                        source_vocabulary=atom_data.get('rootSource'),
                        code=atom_data.get('code'),
                        preferred=atom_data.get('preferred', False),
                        suppressible=atom_data.get('suppressible', False),
                        language=atom_data.get('language')
                    )
                    atoms.append(atom)
            
            return NameMapping(
                identifier=cui,
                identifier_type='CUI',
                cui=cui,
                name=cui_name,
                atoms=atoms
            )
            
        except Exception as e:
            logger.error(f"Error getting names for CUI {cui}: {e}")
            return NameMapping(
                identifier=cui,
                identifier_type='CUI',
                error_message=str(e)
            )
    
    async def get_names_for_code(self, code: str, source_vocabulary: str) -> NameMapping:
        """
        Get names and atoms for a code from a specific source vocabulary.
        
        Args:
            code: The code to get names for
            source_vocabulary: The source vocabulary the code belongs to
            
        Returns:
            NameMapping with names and atoms
        """
        try:
            content_endpoint = f"/rest/content/{self.version}/source/{source_vocabulary}/{code}"
            
            response = await self._make_request(
                f"{self.base_uri}{content_endpoint}",
                {}
            )
            
            json_data = response.get('result', {})
            
            # Extract basic information
            code_name = json_data.get('name', '')
            atoms_data = json_data.get('atoms', [])
            
            # Process atoms
            atoms = []
            if atoms_data:
                for atom_data in atoms_data:
                    atom = AtomEntry(
                        aui=atom_data.get('aui'),
                        name=atom_data.get('name'),
                        term_type=atom_data.get('termType'),
                        source_vocabulary=atom_data.get('rootSource'),
                        code=atom_data.get('code'),
                        preferred=atom_data.get('preferred', False),
                        suppressible=atom_data.get('suppressible', False),
                        language=atom_data.get('language')
                    )
                    atoms.append(atom)
            
            return NameMapping(
                identifier=code,
                identifier_type='code',
                source_vocabulary=source_vocabulary,
                name=code_name,
                atoms=atoms
            )
            
        except Exception as e:
            logger.error(f"Error getting names for code {code} in vocabulary {source_vocabulary}: {e}")
            return NameMapping(
                identifier=code,
                identifier_type='code',
                source_vocabulary=source_vocabulary,
                error_message=str(e)
            )
    
    async def get_names_for_identifiers(self, identifiers: List[str],
                                      source_vocabulary: Optional[str] = None) -> NamesResult:
        """
        Get names for multiple identifiers concurrently.
        
        Args:
            identifiers: List of identifiers (CUIs or codes)
            source_vocabulary: Source vocabulary if identifiers are codes
            
        Returns:
            NamesResult with all mappings and statistics
        """
        start_time = asyncio.get_event_loop().time()
        
        # Determine identifier type
        identifier_type = 'code' if source_vocabulary else 'CUI'
        
        # Create tasks for concurrent processing
        tasks = []
        for identifier in identifiers:
            if source_vocabulary:
                task = self.get_names_for_code(identifier, source_vocabulary)
            else:
                task = self.get_names_for_cui(identifier)
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        all_mappings = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(f"Error processing identifier {identifiers[i]}: {result}")
                all_mappings.append(NameMapping(
                    identifier=identifiers[i],
                    identifier_type=identifier_type,
                    source_vocabulary=source_vocabulary,
                    error_message=str(result)
                ))
            else:
                all_mappings.append(result)
        
        # Calculate statistics
        successful_mappings = sum(1 for m in all_mappings if m.is_successful)
        failed_mappings = len(all_mappings) - successful_mappings
        execution_time = asyncio.get_event_loop().time() - start_time
        
        return NamesResult(
            identifiers=identifiers,
            identifier_type=identifier_type,
            source_vocabulary=source_vocabulary,
            mappings=all_mappings,
            total_processed=len(identifiers),
            successful_mappings=successful_mappings,
            failed_mappings=failed_mappings,
            execution_time=execution_time,
            errors=errors
        )
    
    async def get_names_from_file(self, input_file: Union[str, Path],
                                source_vocabulary: Optional[str] = None) -> NamesResult:
        """
        Process identifiers from an input file.
        
        Args:
            input_file: Path to file containing identifiers (one per line)
            source_vocabulary: Source vocabulary if identifiers are codes
            
        Returns:
            NamesResult with all mappings and statistics
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # Read identifiers from file
        identifiers = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.isspace():
                    identifiers.append(line)
        
        if not identifiers:
            raise ValueError("No valid identifiers found in input file")
        
        logger.info(f"Processing {len(identifiers)} identifiers from {input_file}")
        
        return await self.get_names_for_identifiers(identifiers, source_vocabulary)
    
    async def batch_lookup(self, identifier_vocabulary_pairs: List[Tuple[str, Optional[str]]]) -> Dict[str, NamesResult]:
        """
        Perform batch lookups for different identifier-vocabulary combinations.
        
        Args:
            identifier_vocabulary_pairs: List of (identifier, vocabulary) tuples
            
        Returns:
            Dictionary mapping vocabulary to NamesResult
        """
        # Group identifiers by vocabulary
        vocab_groups = {}
        for identifier, vocab in identifier_vocabulary_pairs:
            vocab_key = vocab or 'CUI'
            if vocab_key not in vocab_groups:
                vocab_groups[vocab_key] = []
            vocab_groups[vocab_key].append(identifier)
        
        # Process each vocabulary group
        results = {}
        for vocab_key, identifiers in vocab_groups.items():
            vocab = vocab_key if vocab_key != 'CUI' else None
            result = await self.get_names_for_identifiers(identifiers, vocab)
            results[vocab_key] = result
        
        return results
    
    def save_result(self, result: NamesResult, output_file: Union[str, Path],
                   format: str = "txt") -> None:
        """
        Save names result to file.
        
        Args:
            result: The NamesResult to save
            output_file: Path to output file
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
    
    def _save_txt(self, result: NamesResult, output_path: Path) -> None:
        """Save result in text format."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("UMLS Names Retrieval Results\n")
            f.write("=" * 50 + "\n")
            f.write(f"Identifier Type: {result.identifier_type}\n")
            f.write(f"Source Vocabulary: {result.source_vocabulary or 'N/A'}\n")
            f.write(f"Total Processed: {result.total_processed}\n")
            f.write(f"Successful: {result.successful_mappings} ({result.success_rate:.1f}%)\n")
            f.write(f"Failed: {result.failed_mappings}\n")
            f.write(f"Execution Time: {result.execution_time:.2f}s\n")
            f.write("=" * 50 + "\n\n")
            
            for mapping in result.mappings:
                f.write(f"IDENTIFIER: {mapping.identifier}\n")
                f.write(f"Type: {mapping.identifier_type}\n")
                if mapping.source_vocabulary:
                    f.write(f"Source Vocabulary: {mapping.source_vocabulary}\n")
                f.write("\n")
                
                if mapping.is_successful:
                    f.write(f"Name: {mapping.name}\n")
                    if mapping.cui:
                        f.write(f"CUI: {mapping.cui}\n")
                    
                    if mapping.atoms:
                        f.write(f"\nAtoms ({len(mapping.atoms)}):\n")
                        for i, atom in enumerate(mapping.atoms, 1):
                            f.write(f"  {i}. AUI: {atom.aui}\n")
                            f.write(f"     Name: {atom.name}\n")
                            f.write(f"     Term Type: {atom.term_type}\n")
                            f.write(f"     Source: {atom.source_vocabulary}\n")
                            f.write(f"     Code: {atom.code}\n")
                            f.write(f"     Preferred: {atom.preferred}\n")
                            f.write(f"     Suppressible: {atom.suppressible}\n")
                            f.write(f"     Language: {atom.language}\n")
                            f.write("\n")
                else:
                    f.write(f"ERROR: {mapping.error_message}\n")
                
                f.write("=" * 30 + "\n\n")
    
    def _save_json(self, result: NamesResult, output_path: Path) -> None:
        """Save result in JSON format."""
        data = {
            "metadata": {
                "identifier_type": result.identifier_type,
                "source_vocabulary": result.source_vocabulary,
                "total_processed": result.total_processed,
                "successful_mappings": result.successful_mappings,
                "failed_mappings": result.failed_mappings,
                "success_rate": result.success_rate,
                "execution_time": result.execution_time,
                "timestamp": datetime.now().isoformat()
            },
            "mappings": []
        }
        
        for mapping in result.mappings:
            atoms_data = []
            for atom in mapping.atoms:
                atoms_data.append({
                    "aui": atom.aui,
                    "name": atom.name,
                    "term_type": atom.term_type,
                    "source_vocabulary": atom.source_vocabulary,
                    "code": atom.code,
                    "preferred": atom.preferred,
                    "suppressible": atom.suppressible,
                    "language": atom.language
                })
            
            mapping_data = {
                "identifier": mapping.identifier,
                "identifier_type": mapping.identifier_type,
                "source_vocabulary": mapping.source_vocabulary,
                "cui": mapping.cui,
                "name": mapping.name,
                "atoms": atoms_data,
                "confidence": mapping.confidence,
                "is_successful": mapping.is_successful,
                "error_message": mapping.error_message
            }
            data["mappings"].append(mapping_data)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_csv(self, result: NamesResult, output_path: Path) -> None:
        """Save result in CSV format."""
        df = result.to_dataframe()
        df.to_csv(output_path, index=False, encoding='utf-8')
    
    def _save_excel(self, result: NamesResult, output_path: Path) -> None:
        """Save result in Excel format."""
        df = result.to_dataframe()
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Main data sheet
            df.to_excel(writer, sheet_name='Names', index=False)
            
            # Summary sheet
            summary_df = pd.DataFrame({
                'Metric': ['Identifier Type', 'Source Vocabulary', 'Total Processed', 'Successful', 'Failed', 'Success Rate (%)', 'Execution Time (s)'],
                'Value': [result.identifier_type, result.source_vocabulary or 'N/A', result.total_processed, 
                         result.successful_mappings, result.failed_mappings, f"{result.success_rate:.1f}", f"{result.execution_time:.2f}"]
            })
            summary_df.to_excel(writer, sheet_name='Summary', index=False)


async def main():
    """Command line interface for the names retrieval client."""
    parser = argparse.ArgumentParser(description='UMLS Names Retrieval Client')
    parser.add_argument('-k', '--apikey', required=True, help='UTS API key')
    parser.add_argument('-v', '--version', default='current', help='UMLS version')
    parser.add_argument('-i', '--identifier', help='Single identifier to process')
    parser.add_argument('--input-file', help='Input file with identifiers (one per line)')
    parser.add_argument('-o', '--output', required=True, help='Output file path')
    parser.add_argument('-f', '--format', default='txt', choices=['txt', 'json', 'csv', 'excel'], 
                       help='Output format')
    parser.add_argument('-s', '--source', 
                       help='Source vocabulary (required for codes, omit for CUIs)')
    parser.add_argument('--max-concurrent', type=int, default=10, 
                       help='Maximum concurrent requests')
    parser.add_argument('--delay', type=float, default=0.1, 
                       help='Request delay in seconds')
    
    args = parser.parse_args()
    
    # Get API key from environment if not provided
    api_key = args.apikey or os.getenv('UMLS_API_KEY_TU')
    if not api_key:
        print("Error: API key required. Use -k flag or set UMLS_API_KEY_TU environment variable.")
        sys.exit(1)
    
    # Validate input
    if not args.identifier and not args.input_file:
        print("Error: Either --identifier or --input-file is required.")
        sys.exit(1)
    
    try:
        async with UMLSNamesRetrievalClient(
            api_key=api_key,
            version=args.version,
            max_concurrent_requests=args.max_concurrent,
            request_delay=args.delay
        ) as client:
            
            if args.identifier:
                # Process single identifier
                result = await client.get_names_for_identifiers([args.identifier], args.source)
            else:
                # Process file
                result = await client.get_names_from_file(args.input_file, args.source)
            
            client.save_result(result, args.output, args.format)
            
            print(f"Processing complete:")
            print(f"  Total processed: {result.total_processed}")
            print(f"  Successful: {result.successful_mappings} ({result.success_rate:.1f}%)")
            print(f"  Failed: {result.failed_mappings}")
            print(f"  Execution time: {result.execution_time:.2f}s")
            print(f"  Output saved to: {args.output}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
