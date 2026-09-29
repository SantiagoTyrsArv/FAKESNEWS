"""Import every module's SQLAlchemy models so Base.metadata is fully
populated in whatever process imports this — regardless of which routers or
tasks that process happens to touch first. Without this, cross-module string
ForeignKeys (e.g. submissions.user_id -> "users.id") fail with
NoReferencedTableError in any process that never imported the referenced
module directly (e.g. the ARQ worker, which never imports the auth module).

Import this for its side effects only: `import app.core.models_registry`.
"""

import app.modules.auth.models  # noqa: F401
import app.modules.pipeline.models  # noqa: F401
import app.modules.sources.models  # noqa: F401
import app.modules.submissions.models  # noqa: F401
