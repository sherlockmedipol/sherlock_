"""
Yerel JSON depolama modulu
Tarama gecmisi ve sonuclari icin dosya yonetimi
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import aiofiles
import uuid

from sherlock_project.result import QueryResult, QueryStatus


HISTORY_INDEX_FILENAME = "search_history.json"


class LocalStorage:
    """Yerel JSON dosya depolama yoneticisi"""

    def __init__(self):
        self.base_dir = Path.home() / '.sherlock'
        self.history_dir = self.base_dir / 'history'
        self.index_file = self.history_dir / HISTORY_INDEX_FILENAME
        self._ensure_directories()

    def _ensure_directories(self):
        """Gerekli dizinleri olustur"""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _generate_scan_id(self) -> str:
        """Benzersiz tarama ID uret"""
        return str(uuid.uuid4())[:8]

    def _get_timestamp(self) -> str:
        """ISO format zaman damgasi"""
        return datetime.now().isoformat()

    def _get_filename(self, username: str) -> str:
        """Tarama dosya adi olustur"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{timestamp}_{username}.json"

    def _result_to_dict(self, result: QueryResult) -> Dict[str, Any]:
        """QueryResult'u dict'e cevir"""
        http_status = None
        if isinstance(result.context, dict):
            http_status = result.context.get('http_status')
        return {
            'site_name': result.site_name,
            'url_user': result.site_url_user,
            'status': result.status.value if result.status else 'unknown',
            'http_status': http_status,
            'response_time': result.query_time,
            'context': result.context
        }

    def _load_index(self) -> List[Dict[str, Any]]:
        """Load the search history index from the index file."""
        if not self.index_file.exists():
            return []
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except (json.JSONDecodeError, IOError, ValueError):
            return []

    def _save_index(self, index: List[Dict[str, Any]]) -> None:
        """Persist the search history index to the index file."""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def load_search_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load search history from the consolidated index file."""
        index = self._load_index()
        index.sort(key=lambda h: h.get("timestamp", ""), reverse=True)
        if limit:
            return index[:limit]
        return index

    async def save_scan(
        self,
        username: str,
        results: List[QueryResult],
        total_sites: int,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Tarama sonuclarini kaydet.
        Only saves if the search produced at least one claimed result.
        Returns None for empty searches.
        """
        found_count = sum(
            1 for r in results
            if r.status == QueryStatus.CLAIMED
        )

        if found_count == 0:
            return None

        scan_id = self._generate_scan_id()
        filename = self._get_filename(username)
        filepath = self.history_dir / filename

        data = {
            'scan_id': scan_id,
            'username': username,
            'started_at': self._get_timestamp(),
            'completed_at': datetime.now().isoformat(),
            'total_sites': total_sites,
            'found_count': found_count,
            'metadata': metadata or {},
            'results': [self._result_to_dict(r) for r in results]
        }

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))

        index = self._load_index()
        index.append({
            "query": username,
            "timestamp": data["completed_at"],
            "resultCount": found_count,
            "scan_id": scan_id,
            "total_sites": total_sites,
            "_filepath": str(filepath.resolve()),
        })
        self._save_index(index)

        return str(filepath)

    async def load_scan(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Tarama sonuclarini yukle."""
        path = Path(filepath)
        if not path.exists():
            return None
        try:
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except (json.JSONDecodeError, IOError):
            return None

    async def get_scan_history_async(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Tarama gecmisini async listele (aiofiles ile)"""
        scans = []
        if not self.history_dir.exists():
            return scans
        for filepath in sorted(self.history_dir.glob('*.json'), reverse=True):
            if filepath.name == HISTORY_INDEX_FILENAME:
                continue
            try:
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                    data['_filepath'] = str(filepath)
                    scans.append(data)
            except Exception:
                continue
        if limit:
            scans = scans[:limit]
        return scans

    def get_scan_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Tarama gecmisini listele (senkron)"""
        scans = []
        if not self.history_dir.exists():
            return scans
        for filepath in sorted(self.history_dir.glob('*.json'), reverse=True):
            if filepath.name == HISTORY_INDEX_FILENAME:
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['_filepath'] = str(filepath)
                    scans.append(data)
            except Exception:
                continue
        if limit:
            scans = scans[:limit]
        return scans

    async def delete_scan_async(self, filepath: str) -> bool:
        """Tarama kaydini async sil (aiofiles ile)"""
        try:
            path = Path(filepath)
            if path.exists():
                import aiofiles.os as aio_os
                await aio_os.unlink(filepath)
            index = self._load_index()
            target_path = str(Path(filepath).resolve())
            index = [e for e in index if e.get("_filepath") != target_path]
            self._save_index(index)
            return True
        except Exception:
            return False

    def delete_scan(self, filepath: str) -> bool:
        """Tarama kaydini sil (senkron)"""
        try:
            Path(filepath).unlink()
            index = self._load_index()
            target_path = str(Path(filepath).resolve())
            index = [e for e in index if e.get("_filepath") != target_path]
            self._save_index(index)
            return True
        except Exception:
            return False

    async def get_stats_async(self) -> Dict[str, Any]:
        """Depolama istatistikleri (async versiyon)"""
        scans = await self.get_scan_history_async()
        total_scans = len(scans)
        total_found = sum(s.get('found_count', 0) for s in scans)
        unique_usernames = len(set(s.get('username') for s in scans))
        return {
            'total_scans': total_scans,
            'total_found_accounts': total_found,
            'unique_usernames': unique_usernames,
            'storage_path': str(self.history_dir)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Depolama istatistikleri (senkron)"""
        scans = self.get_scan_history()
        total_scans = len(scans)
        total_found = sum(s.get('found_count', 0) for s in scans)
        unique_usernames = len(set(s.get('username') for s in scans))
        return {
            'total_scans': total_scans,
            'total_found_accounts': total_found,
            'unique_usernames': unique_usernames,
            'storage_path': str(self.history_dir)
        }