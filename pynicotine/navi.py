from concurrent import futures
import time
import grpc
import threading
import asyncio
import logging
from typing import Iterable

from pynicotine import config, core
from pynicotine.events import events
import pynicotine.search as s
from google.ads.googleads import util

# correct generated files import (pynicotine/nicotine_pb2_grpc.py):
# import pynicotine.nicotine_pb2 as nicotine__pb2
import pynicotine.nicotine_pb2 as nicotine_pb2
import pynicotine.nicotine_pb2_grpc as nicotine_pb2_grpc
from pynicotine.slskmessages import TransferRejectReason, increment_token
from pynicotine.transfers import TransferStatus

# Coroutines to be invoked when the event loop is shutting down.
_cleanup_coroutines = []


class Downloader(nicotine_pb2_grpc.DownloaderServicer):
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
        self.token = 0

    def __callback__(self, search, username, filelist):
        with self.lock:
            if search not in self.results:
                self.results[search] = {username: filelist}
            else:
                searchResultsSoFar = self.results[search]
                if username not in searchResultsSoFar:
                    self.results[search] = {username: filelist}
                else:
                    self.results[search][username].extend(filelist)

    async def Search(
        self,
        request: nicotine_pb2.SearchRequest,
        context: grpc.aio.ServicerContext,
    ) -> Iterable[nicotine_pb2.SearchResponse]:  # type: ignore
        search_term, room, users = core.search.process_search_term(
            request.term, "global"
        )

        self.token = increment_token(self.token)
        search = core.search.add_search(search_term, "global", room, users)

        events.connect(str(search.token), self.__callback__)

        if config.sections["searches"]["enable_history"]:
            items = config.sections["searches"]["history"]

            if search.term_sanitized in items:
                items.remove(search.term_sanitized)

            items.insert(0, search.term_sanitized)

            del items[200:]
            config.write_configuration()

        core.search.do_global_search(search.term_transmitted)

        events.emit("add-search", search.token, search, False)

        # Wait for 30 seconds for search results to collect.
        for i in range(30):
            with self.lock:
                results = self.results.get(str(search.token))
                if results is not None:
                    for user in results:
                        for file in results[user]:
                            f = nicotine_pb2.File(username=user, filepath=file[1])
                            yield nicotine_pb2.SearchResponse(response=f)

                    # Remove already sent results from the dictionary.
                    self.results[str(search.token)][user].clear()

            time.sleep(1)

        # Is this even needed? Check garbage collection in Python.
        with self.lock:
            del self.results[str(search.token)]

        core.search.remove_search(search.token)

        events.disconnect(str(search.token), self.__callback__)

    async def Download(
        self,
        request: nicotine_pb2.DownloadRequest,
        context: grpc.aio.ServicerContext,
    ) -> Iterable[nicotine_pb2.DownloadResponse]:  # type: ignore
        transfer = core.downloads.transfers.get(
            request.request.username + request.request.filepath
        )

        if transfer is not None:
            core.downloads.enqueue_download(
                request.request.username, request.request.filepath
            )

            transfer = core.downloads.transfers.get(
                request.request.username + request.request.filepath
            )

        for i in range(999999999999999):
            exitFor = False
            match transfer.status:
                case (
                    TransferStatus.QUEUED | TransferStatus.PAUSED,
                    TransferStatus.USER_LOGGED_OFF
                    | TransferStatus.GETTING_STATUS
                    | TransferStatus.CONNECTION_CLOSED
                    | TransferStatus.CONNECTION_TIMEOUT,
                ):
                    yield nicotine_pb2.DownloadResponse(
                        status=nicotine_pb2.DownloadStatus(
                            status=nicotine_pb2.DownloadStatus.Status.QUEUED
                        )
                    )
                    core.downloads.retry_download(transfer)
                    transfer = core.downloads.transfers.get(
                        request.request.username + request.request.filepath
                    )
                    
                case TransferStatus.TRANSFERRING:
                    yield nicotine_pb2.DownloadResponse(
                        status=nicotine_pb2.DownloadStatus(
                            status=nicotine_pb2.DownloadStatus.Status.DOWNLOADING
                        )
                    )

                case TransferStatus.FINISHED:
                    yield nicotine_pb2.DownloadResponse(
                        status=nicotine_pb2.DownloadStatus(
                            status=nicotine_pb2.DownloadStatus.Status.COMPLETED
                        )
                    )
                    exitFor = True

                case (
                    TransferRejectReason.CANCELLED
                    | TransferRejectReason.FILE_READ_ERROR
                    | TransferRejectReason.FILE_NOT_SHARED
                    | TransferRejectReason.BANNED
                    | TransferRejectReason.PENDING_SHUTDOWN
                    | TransferRejectReason.TOO_MANY_FILES
                    | TransferRejectReason.TOO_MANY_MEGABYTES
                    | TransferRejectReason.DISALLOWED_EXTENSION
                    | TransferStatus.DOWNLOAD_FOLDER_ERROR
                ):
                    yield nicotine_pb2.DownloadResponse(
                        status=nicotine_pb2.DownloadStatus(
                            status=nicotine_pb2.DownloadStatus.Status.CANCELLED
                        )
                    )
                    exitFor = True

            if exitFor:
                break

            time.sleep(1)


async def serve() -> None:
    server = grpc.aio.server()
    nicotine_pb2_grpc.add_DownloaderServicer_to_server(Downloader(), server)
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    logging.info("Starting server on %s", listen_addr)
    await server.start()

    async def server_graceful_shutdown():
        logging.info("Starting graceful shutdown...")
        # Shuts down the server with 5 seconds of grace period. During the
        # grace period, the server won't accept new connections and allow
        # existing RPCs to continue within the grace period.
        await server.stop(5)

    _cleanup_coroutines.append(server_graceful_shutdown())
    await server.wait_for_termination()


def nico():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(serve())
    finally:
        loop.run_until_complete(*_cleanup_coroutines)
        loop.close()
