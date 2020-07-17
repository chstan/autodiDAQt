import asyncio
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from daquiri.utils import find_conflict_free_matches, gather_dict, run_on_loop

from . import lakeshore, newport, srs

__all__ = (
    "identification_protocols",
    "idn_patterns",
    "identify_resource",
    "idn_string_for",
    "identify_all_instruments",
)


identification_protocols = {}
idn_patterns = {}

for manufacturer in {newport, srs, lakeshore}:
    identification_protocols.update(manufacturer.identification_protocols)
    idn_patterns.update(manufacturer.idn_patterns)


async def identify_all_instruments(instrument_map, manager=None):
    """
    Walks through resources and instruments and tries to match them to each other. Currently we don't
    pay any attention to matching strategies other than results of IDN strings, and also we do not
    take care to explicit addresses passed to instruments. We will cross this bridge when we come to it.
    """

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=20)

    idn_futures = {}
    handles_by_address = {}

    unidentified = set(instrument_map.keys())
    resources = {}
    # resources = resource_manager.list_resources_info()

    for k, v in resources.items():
        try:
            resource = manager.open_resource(k)
            idn_futures[k] = loop.run_in_executor(
                executor, run_on_loop, identify_resource, resource
            )
            handles_by_address[k] = resource
        except Exception as e:
            pass

    # We use a threadpool executor because the library we use for communication to resources
    # does not support asyncio, therefore we want to avoid incurring too much IO overhead by doing
    # this on a single thread

    idn_results = await gather_dict(idn_futures)

    options = defaultdict(list)

    for address, (string, method) in idn_results.items():
        if isinstance(method, str):
            # we actually used IDN? or *IDN?, so go and check the idn_patterns
            for option in unidentified:
                instrument = instrument_map[option]
                idn_pattern = idn_string_for(instrument)
                if idn_pattern.match(string):
                    options[option].append(address)
        else:
            # don't actually support anything else right now, so we will wait here
            pass

    # close all
    for handle in handles_by_address.values():
        handle.close()

    return find_conflict_free_matches(options)


def idn_string_for(front_panel):
    return idn_patterns[front_panel.instrument_cls.__name__]


async def identify_resource(resource, additional_identification_modes=None):
    if additional_identification_modes is None:
        additional_identification_modes = identification_protocols

    best_response = None
    best_dialogue = None

    for dialogue in ["*IDN?", "?IDN"]:
        try:
            response = resource.ask(dialogue)
            if best_response is None or len(response) > len(best_response):
                best_response = response
                best_dialogue = dialogue
        except Exception:
            continue

    if best_response is None:
        # try the fallback dialogues
        for (
            instrument_option,
            identification_fn,
        ) in additional_identification_modes.items():
            response = identification_fn(resource)
            if response:
                best_response = response
                best_dialogue = instrument_option
                break

    return best_response, best_dialogue
