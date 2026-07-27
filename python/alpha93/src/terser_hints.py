preserve_docstring = lambda x: x
preserve_annotations = lambda x: x
constant = lambda x: x()


__all__ = ("preserve_docstring", "preserve_annotations", "constant")
