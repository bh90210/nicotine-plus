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

    def Search(
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

        deleteSearchTermFromDictionary = False
        # Wait for 120 seconds for search results to collect.
        for i in range(120):
            with self.lock:
                results = self.results.get(str(search.token))
                if results is not None:
                    deleteSearchTermFromDictionary = True
                    users = []
                    for user in results:
                        files = []
                        for file in results[user]:
                            files.append(
                                nicotine_pb2.File(filepath=file[1], size=file[2])
                            )

                        yield nicotine_pb2.SearchResponse(
                            username=user, user_files=files
                        )
                        users.append(user)

                    for user in users:
                        self.results[str(search.token)].pop(user)

            time.sleep(1)

        if deleteSearchTermFromDictionary:
            with self.lock:
                del self.results[str(search.token)]

        core.search.remove_search(search.token)

        events.disconnect(str(search.token), self.__callback__)

    def Download(
        self,
        request: nicotine_pb2.DownloadRequest,
        context: grpc.aio.ServicerContext,
    ) -> Iterable[nicotine_pb2.DownloadResponse]:  # type: ignore
        # Check to see if a transfer already exists. This situation can occur
        # due to a broken connection etc.
        transfer = core.downloads.transfers.get(
            request.username + request.file.filepath
        )

        if request.file.quality == "-1":
            core.downloads._abort_transfer(
                transfer, TransferRejectReason.CANCELLED, update_parent=False
            )

            events.emit("abort-downloads", transfer, TransferRejectReason.CANCELLED)

            yield nicotine_pb2.DownloadResponse(
                status=nicotine_pb2.DownloadStatus(
                    status=nicotine_pb2.DownloadStatus.Status.CANCELLED
                )
            )
            return

        if transfer is None:
            core.downloads.enqueue_download(request.username, request.file.filepath)

        transferring = False
        while True:
            transfer = core.downloads.transfers.get(
                request.username + request.file.filepath
            )

            match transfer.status:
                case (
                    TransferStatus.QUEUED
                    | TransferStatus.PAUSED
                    | TransferStatus.USER_LOGGED_OFF
                    | TransferStatus.GETTING_STATUS
                    | TransferStatus.CONNECTION_CLOSED
                    | TransferStatus.CONNECTION_TIMEOUT
                ):
                    yield nicotine_pb2.DownloadResponse(
                        status=nicotine_pb2.DownloadStatus(
                            status=nicotine_pb2.DownloadStatus.Status.QUEUED
                        )
                    )

                    transferring = False

                    time.sleep(4)

                    core.downloads.retry_download(transfer)

                case TransferStatus.TRANSFERRING:
                    if transferring is False:
                        transferring = True
                        yield nicotine_pb2.DownloadResponse(
                            status=nicotine_pb2.DownloadStatus(
                                status=nicotine_pb2.DownloadStatus.Status.DOWNLOADING
                            )
                        )

                    yield nicotine_pb2.DownloadResponse(
                        progress=nicotine_pb2.DownloadProgress(
                            progress=self._get_percent(
                                transfer.current_byte_offset, transfer.size
                            )
                        )
                    )

                case TransferStatus.FINISHED:
                    yield nicotine_pb2.DownloadResponse(
                        status=nicotine_pb2.DownloadStatus(
                            status=nicotine_pb2.DownloadStatus.Status.COMPLETED
                        )
                    )

                    break

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

                    break

            time.sleep(1)

    def _get_percent(self, current_byte_offset, size):
        if current_byte_offset > size or size <= 0:
            return 100

        # Multiply first to avoid decimals
        return (100 * current_byte_offset) // size


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor())
    nicotine_pb2_grpc.add_DownloaderServicer_to_server(Downloader(), server)
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    server.start()
    logging.info("Starting server on %s", listen_addr)
    server.wait_for_termination()
