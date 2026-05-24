"""Decorator mixins for LocalProvider.

This module provides mixin classes that add decorator functionality
to LocalProvider for tools, resources, templates, and prompts.
"""

from ._prompts import PromptDecoratorMixin
from ._resources import ResourceDecoratorMixin
from ._tools import ToolDecoratorMixin

__all__ = (
    "PromptDecoratorMixin",
    "ResourceDecoratorMixin",
    "ToolDecoratorMixin",
)
