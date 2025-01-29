from concurrent import futures
import time
import grpc
import threading
import asyncio
import logging

from pynicotine import config, core
from pynicotine.events import events
import pynicotine.search as s

# correct generated files import (pynicotine/navi_pb2_grpc.py):
# import pynicotine.navi_pb2 as navi__pb2
import pynicotine.navi_pb2 as navi_pb2
import pynicotine.navi_pb2_grpc as navi_pb2_grpc
from pynicotine.slskmessages import increment_token

# Coroutines to be invoked when the event loop is shutting down.
_cleanup_coroutines = []


class Downloader(navi_pb2_grpc.DownloaderServicer):
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
        request: navi_pb2.SearchRequest,
        context: grpc.aio.ServicerContext,
    ) -> navi_pb2.SearchReply:  # type: ignore
        # Validate search term and run it through plugins
        search_term, room, users = core.search.process_search_term(
            request.term, "global"
        )

        # Get a new search token
        self.token = increment_token(self.token)
        search = core.search.add_search(search_term, "global", room, users)

        events.connect(str(search.token), self.__callback__)

        if config.sections["searches"]["enable_history"]:
            items = config.sections["searches"]["history"]

            if search.term_sanitized in items:
                items.remove(search.term_sanitized)

            items.insert(0, search.term_sanitized)

            # Clear old items
            del items[200:]
            config.write_configuration()

        core.search.do_global_search(search.term_transmitted)

        events.emit("add-search", search.token, search, False)

        for i in range(30):
            results = self.results.get(str(search.token))
            if results is not None:
                with self.lock:
                    for user in results:
                        for file in results[user]:
                            yield navi_pb2.SearchReply(username=user, file=file[1])

                    self.results[str(search.token)][user].clear()

            time.sleep(1)

        # Is this even needed? Check garbage collection in Python.
        with self.lock:
            del self.results[str(search.token)]

        core.search.remove_search(search.token)

        events.disconnect(str(search.token), self.__callback__)

        context.done()

    async def Download(
        self,
        request: navi_pb2.DownloadRequest,
        context: grpc.aio.ServicerContext,
    ) -> navi_pb2.DownloadReply:
        core.downloads.enqueue_download(request.username, request.file)

        return navi_pb2.DownloadReply(result=0)


async def serve() -> None:
    server = grpc.aio.server()
    navi_pb2_grpc.add_DownloaderServicer_to_server(Downloader(), server)
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
