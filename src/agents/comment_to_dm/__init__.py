"""Comment-to-DM automation — triggered by Zernio ``comment.received``.

See ``runner.handle_comment`` for the entry-point used by the webhook
dispatcher.
"""

from src.agents.comment_to_dm.runner import handle_comment

__all__ = ["handle_comment"]
