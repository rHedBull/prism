from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceInstance:
    name: str
    url: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_health_check: float = 0.0
    consecutive_failures: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


class ServiceRegistry:
    def __init__(self, health_check_interval: float = 15.0) -> None:
        self._services: dict[str, ServiceInstance] = {}
        self._lock = asyncio.Lock()
        self._health_check_interval = health_check_interval
        self._health_check_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Service registry started with %.1fs health check interval", self._health_check_interval)

    async def stop(self) -> None:
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Service registry stopped")

    async def register(self, name: str, url: str, metadata: dict[str, str] | None = None) -> ServiceInstance:
        async with self._lock:
            instance = ServiceInstance(
                name=name,
                url=url.rstrip("/"),
                metadata=metadata or {},
            )
            self._services[name] = instance
            logger.info("Registered service: %s -> %s", name, url)
            return instance

    async def deregister(self, name: str) -> bool:
        async with self._lock:
            if name in self._services:
                del self._services[name]
                logger.info("Deregistered service: %s", name)
                return True
            return False

    async def get_service_url(self, name: str) -> str | None:
        async with self._lock:
            instance = self._services.get(name)
            if instance is None:
                return None
            if instance.status == ServiceStatus.UNHEALTHY:
                logger.warning("Service %s is unhealthy, returning URL anyway for retry logic", name)
            return instance.url

    async def get_service(self, name: str) -> ServiceInstance | None:
        async with self._lock:
            return self._services.get(name)

    async def get_all_services(self) -> dict[str, ServiceInstance]:
        async with self._lock:
            return dict(self._services)

    async def health_check_all(self) -> dict[str, ServiceStatus]:
        results: dict[str, ServiceStatus] = {}
        services = await self.get_all_services()

        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = {
                name: self._check_service_health(client, instance)
                for name, instance in services.items()
            }
            for name, coro in tasks.items():
                results[name] = await coro

        return results

    async def _check_service_health(
        self, client: httpx.AsyncClient, instance: ServiceInstance
    ) -> ServiceStatus:
        try:
            response = await client.get(f"{instance.url}/health")
            if response.status_code == 200:
                async with self._lock:
                    instance.status = ServiceStatus.HEALTHY
                    instance.consecutive_failures = 0
                    instance.last_health_check = time.time()
                return ServiceStatus.HEALTHY
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning("Health check failed for %s: %s", instance.name, exc)

        async with self._lock:
            instance.consecutive_failures += 1
            instance.last_health_check = time.time()
            if instance.consecutive_failures >= 3:
                instance.status = ServiceStatus.UNHEALTHY
            else:
                instance.status = ServiceStatus.UNKNOWN
        return instance.status

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                await self.health_check_all()
            except Exception:
                logger.exception("Error during health check cycle")
            await asyncio.sleep(self._health_check_interval)
