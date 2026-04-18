"""
walker.py — Generic Tree Walker (Task 1)
=========================================
Structure-agnostic recursive traversal of parsed ASN.1 trees.
No hardcoded keys, no fixed depth assumptions.

Yields (path, key, value) tuples for every node in the tree,
enabling gap detection and pattern-based analysis without
coupling to specific data shapes.
"""

from __future__ import annotations
from typing import Any, Generator, List, Tuple


def walk(node: Any, path: list = None) -> Generator[Tuple[List, str, Any], None, None]:
    """
    Recursively traverse any nested dict/list structure.

    Yields:
        (path, key, value) where:
        - path: list of keys/indices leading to this node
        - key:  the current key name (str for dicts, int index for lists)
        - value: the value at this node

    Example:
        for path, key, value in walk(parsed_json):
            print(f"{'.'.join(map(str, path))}.{key} = {value}")
    """
    if path is None:
        path = []

    if isinstance(node, dict):
        for key, value in node.items():
            current_path = path + [key]
            yield path, key, value
            # Always recurse deeper — walker is agnostic
            yield from walk(value, current_path)

    elif isinstance(node, list):
        for idx, item in enumerate(node):
            current_path = path + [idx]
            yield path, idx, item
            yield from walk(item, current_path)


def walk_dicts_only(node: Any, path: list = None) -> Generator[Tuple[List, dict], None, None]:
    """
    Yield (path, dict_node) for every dict found in the tree.
    Useful for finding entries that contain specific keys.
    """
    if path is None:
        path = []

    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from walk_dicts_only(value, path + [key])

    elif isinstance(node, list):
        for idx, item in enumerate(node):
            yield from walk_dicts_only(item, path + [idx])


def collect_by_pattern(node: Any, predicate) -> list:
    """
    Collect all (path, key, value) tuples where predicate(key, value) is True.

    Args:
        node: root of the tree to search
        predicate: callable(key, value) -> bool

    Returns:
        list of (path, key, value) matches
    """
    matches = []
    for path, key, value in walk(node):
        if isinstance(key, str) and predicate(key, value):
            matches.append((path, key, value))
    return matches
