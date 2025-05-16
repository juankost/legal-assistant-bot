import functools
import time
import logging
from typing import Callable, TypeVar, ParamSpec


P = ParamSpec("P")
R = TypeVar("R")


def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries == max_retries:
                        logging.error(f"Failed after {max_retries} attempts. Final error: {str(e)}")
                        raise
                    logging.warning(
                        f"Attempt {retries} failed. Retrying in {delay} seconds... Error: {str(e)}"
                    )
                    time.sleep(delay)
            return func(*args, **kwargs)  # Final attempt

        return wrapper

    return decorator
