import functools
from importlib.util import find_spec
from typing import Union

# this is a cache to speed up our checks
_installed_libs = []


def requirement_decorator(requirement: str):
    """
    Decorator to require a library.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # did we already check for the requirement
            if requirement in _installed_libs:
                return func(*args, **kwargs)

            # find in modules
            spec = find_spec(requirement)
            if spec is None:
                raise ImportError(f"{requirement} is not installed. Please install {requirement} to use this function.")
            _installed_libs.append(requirement)

            return func(*args, **kwargs)
        return wrapper
    return decorator


def requires_numpy():
    return requirement_decorator("numpy")
def requires_cv2():
    return requirement_decorator("cv2")

def requires(requirements: Union[list, tuple, str], *args):
    """
    Decorator to require multiple libraries.
    """
    if isinstance(requirements, str):
        requirements = [requirements]
    elif isinstance(requirements, tuple):
        requirements = list(requirements)

    for arg in args:
        requirements.append(arg)

    req_func = lambda x: x  # identity function if no reqs given
    for req in requirements:
        req_func = requirement_decorator(req)

    return req_func
