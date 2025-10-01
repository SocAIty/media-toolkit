from collections.abc import Iterable, Sized
import inspect


def SimpleGeneratorWrapper(iterable, length: int = None) -> 'GeneratorWrapper':
    """
    Factory function to create a SimpleGeneratorWrapper from any iterable.
    
    Args:
        iterable: Any iterable, generator function, or existing SimpleGeneratorWrapper
        length: Optional length hint for progress tracking
        
    Returns:
        SimpleGeneratorWrapper instance
    """
    if isinstance(iterable, GeneratorWrapper):
        # If it's already wrapped, return a new wrapper with the same source
        return GeneratorWrapper(iterable._source, length if length is not None else iterable._length)
    
    return GeneratorWrapper(iterable, length)


class GeneratorWrapper:
    """
    Wraps any iterable or generator function into an Iterator with optional length support (for tqdm or similar progress bars).
    It will yield None for any error in the iterable.
    """
    def __init__(self, iterable, length: int = None):
        if callable(iterable) and inspect.isgeneratorfunction(iterable):
            self._source = iterable
        elif isinstance(iterable, Iterable):
            self._source = iterable
        else:
            raise TypeError(f"{type(iterable)} is not iterable")
        
        # Determine length once
        if isinstance(iterable, Sized):
            self._length = len(iterable)
        elif length is not None:
            self._length = length
        else:
            self._length = None

        # Add length property for compatibility with objects that expect __len__
        if self._length is not None:
            self.__len__ = lambda: self._length

        self._count = 0
        self._iterator = None

    def __iter__(self):
        # Create fresh iterator each time
        if callable(self._source) and inspect.isgeneratorfunction(self._source):
            source = self._source()
        else:
            source = self._source
        
        self._iterator = iter(source)
        self._count = 0
        return self
    
    def __next__(self):
        if self._iterator is None:
            # Auto-initialize if not already done
            self.__iter__()
        try:
            item = next(self._iterator)
            self._count += 1
            return item
        except StopIteration:
            raise
        except Exception as e:
            print(f"Error generating item {self._count} in generator: {e}")
            self._count += 1
            return None
