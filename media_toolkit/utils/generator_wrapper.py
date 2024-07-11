class SimpleGeneratorWrapper:
    """
    Transforms a generator function into an iterable object with a length property.
    This is useful for example in tqdm
    """
    def __init__(self, generator, length):
        self.generator = generator
        self.length = length

    def __iter__(self):
        return self.generator

    def __len__(self):
        return self.length
