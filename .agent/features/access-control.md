# Access Control Architecture - Feature Scratchpad

## Overview

Implement a sophisticated access control system for mcp-refcache that supports:
- Identity-aware actors (not just roles)
- Namespace ownership enforcement
- Session binding for MCP integration
- Backwards compatibility with existing `actor: Literal["user", "agent"]`

## Architecture Decision: Hybrid RBAC + Namespace Ownership

Rejected alternatives:
- **Pure ABAC**: Overkill, requires complex policy engine
- **Pure ACL**: Verbose, doesn't scale well
- **Pure RBAC**: Current state, insufficient for identity tracking

Chosen approach:
- RBAC for role-based defaults (existing behavior)
- Structured Actor with optional identity
- Namespace patterns imply ownership (built-in ABAC rules)
- Optional ACL overrides for fine-grained control

---

## Core Components

### 1. Actor (Identity-Aware)

```python
class ActorType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"  # Internal/admin operations

class Actor(Protocol):
    """Identity-aware actor for access control."""
    
    @property
    def type(self) -> ActorType: ...
    
    @property
    def id(self) -> str | None: ...
    
    @property
    def session_id(self) -> str | None: ...
    
    def matches(self, pattern: str) -> bool:
        """Check if actor matches a pattern like 'user:alice' or 'agent:*'."""
        ...
```

### 2. AccessPolicy (Enhanced)

```python
class AccessPolicy(BaseModel):
    # === Existing RBAC (unchanged) ===
    user_permissions: Permission = Permission.FULL
    agent_permissions: Permission = Permission.READ | Permission.EXECUTE
    
    # === NEW: Ownership ===
    owner: str | None = None  # "user:alice" or "agent:claude-123"
    owner_permissions: Permission = Permission.FULL
    
    # === NEW: ACL Overrides ===
    allowed_actors: frozenset[str] | None = None  # Whitelist
    denied_actors: frozenset[str] | None = None   # Blacklist
    
    # === NEW: Session binding ===
    bound_session: str | None = None  # Lock to specific session
```

### 3. PermissionChecker (Protocol for DI)

```python
class PermissionChecker(Protocol):
    """Protocol for permission checking strategies."""
    
    def check(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Actor,
        namespace: str,
    ) -> None:
        """Check permission, raise PermissionError if denied."""
        ...
    
    def has_permission(
        self,
        policy: AccessPolicy,
        required: Permission,
        actor: Actor,
        namespace: str,
    ) -> bool:
        """Check permission, return bool instead of raising."""
        ...
```

### 4. NamespaceResolver (Protocol for DI)

```python
class NamespaceResolver(Protocol):
    """Protocol for namespace ownership resolution."""
    
    def validate_access(self, namespace: str, actor: Actor) -> bool:
        """Check if actor can access this namespace."""
        ...
    
    def get_owner(self, namespace: str) -> str | None:
        """Extract owner from namespace pattern."""
        ...
    
    def is_session_scoped(self, namespace: str) -> bool:
        """Check if namespace is session-scoped."""
        ...
```

---

## Namespace Ownership Rules

| Pattern | Rule | Example |
|---------|------|---------|
| `public` | No restriction | Anyone can access |
| `session:<id>` | `actor.session_id == id` | `session:abc123` |
| `user:<id>` | `actor.type == USER and actor.id == id` | `user:alice` |
| `agent:<id>` | `actor.type == AGENT and actor.id == id` | `agent:claude-1` |
| `shared:<group>` | Future: group membership | `shared:team-alpha` |

---

## Permission Resolution Algorithm

```
1. DENY if actor in denied_actors
2. DENY if bound_session set and actor.session_id != bound_session
3. DENY if namespace ownership violated
4. ALLOW if actor in allowed_actors (bypass role check)
5. ALLOW with owner_permissions if actor == owner
6. ALLOW/DENY based on role permissions (user_permissions/agent_permissions)
```

---

## Implementation Plan

### Phase 1: Core Abstractions (Protocols) ✅ COMPLETE
- [x] Create `src/mcp_refcache/access/__init__.py`
- [x] Create `src/mcp_refcache/access/actor.py` - ActorType enum, Actor protocol + default impl
- [x] Create `src/mcp_refcache/access/checker.py` - PermissionChecker protocol
- [x] Create `src/mcp_refcache/access/namespace.py` - NamespaceResolver protocol
- [x] Write tests for all protocols (139 tests)

### Phase 2: Default Implementations ✅ COMPLETE
- [x] `DefaultActor` - Pydantic model implementing Actor protocol
- [x] `DefaultPermissionChecker` - Implements the resolution algorithm
- [x] `DefaultNamespaceResolver` - Implements namespace pattern rules
- [x] Integration tests

### Phase 3: AccessPolicy Enhancement ✅ COMPLETE
- [x] Add new fields to AccessPolicy (backwards compatible)
  - `owner: str | None` - Owner identity
  - `owner_permissions: Permission` - Permissions for owner
  - `allowed_actors: frozenset[str] | None` - Explicit allow list
  - `denied_actors: frozenset[str] | None` - Explicit deny list
  - `bound_session: str | None` - Session binding
- [x] Validator for set -> frozenset conversion
- [x] All existing tests still pass (backwards compatible)

### Phase 4: RefCache Integration (NEXT)
- [ ] Update `_check_permission` to use PermissionChecker protocol
- [ ] Add optional DI for checker/resolver in RefCache.__init__
- [ ] Backwards compat: accept both `actor: str` and `actor: Actor`
- [ ] Integration tests with RefCache

### Phase 5: Audit Logging (Optional)
- [ ] Define AuditLogger protocol
- [ ] Hook into permission checks
- [ ] Default no-op implementation

---

## Session Log

### Session 1: Core Access Control Implementation
**Status**: ✅ Complete

**Created Files**:
- `src/mcp_refcache/access/__init__.py` - Module exports
- `src/mcp_refcache/access/actor.py` - Actor protocol + DefaultActor (362 lines)
- `src/mcp_refcache/access/namespace.py` - NamespaceResolver + DefaultNamespaceResolver (354 lines)
- `src/mcp_refcache/access/checker.py` - PermissionChecker + DefaultPermissionChecker (421 lines)
- `tests/test_access_actor.py` - 47 tests
- `tests/test_access_namespace.py` - 47 tests  
- `tests/test_access_checker.py` - 45 tests

**Modified Files**:
- `src/mcp_refcache/permissions.py` - Added 5 new fields to AccessPolicy
- `src/mcp_refcache/__init__.py` - Export new access control types

**Test Results**: 249 tests passing, 92% coverage

---

## File Structure

```
src/mcp_refcache/
├── access/
│   ├── __init__.py          # Public exports
│   ├── actor.py             # ActorType, Actor protocol, DefaultActor
│   ├── checker.py           # PermissionChecker protocol, DefaultPermissionChecker
│   └── namespace.py         # NamespaceResolver protocol, DefaultNamespaceResolver
├── permissions.py           # Permission enum, AccessPolicy (enhanced)
└── cache.py                 # RefCache (updated to use protocols)
```

---

## Backwards Compatibility

```python
# Old code (still works)
cache.get(ref_id, actor="user")
cache.get(ref_id, actor="agent")

# Internally converted to:
cache.get(ref_id, actor=DefaultActor.user())
cache.get(ref_id, actor=DefaultActor.agent())

# New code (identity-aware)
cache.get(ref_id, actor=DefaultActor.user(id="alice", session_id="sess-123"))
cache.get(ref_id, actor=DefaultActor.agent(id="claude-instance-1"))
```

---

## Open Questions

1. **Wildcards in ACLs**: Support `agent:*` to allow all agents? 
   - Decision: Yes, simple glob matching on actor patterns

2. **Group membership**: Support `group:team-alpha` patterns?
   - Decision: Defer to v2, keep it simple for now

3. **Namespace hierarchy inheritance**: Should `user:alice:session:123` inherit from `user:alice`?
   - Decision: Defer, start with flat namespace patterns

4. **Audit logging**: Separate protocol or callback on PermissionChecker?
   - Decision: Separate AuditLogger protocol, optional injection

---

## Test Strategy

1. **Unit tests** for each protocol implementation
2. **Property-based tests** for permission resolution (hypothesis)
3. **Integration tests** with RefCache
4. **Backwards compatibility tests** - ensure old code paths work

---

## Current Session TODO

- [x] Create this feature scratchpad
- [x] Create `src/mcp_refcache/access/` directory
- [x] Define Actor protocol and ActorType enum
- [x] Define PermissionChecker protocol  
- [x] Define NamespaceResolver protocol
- [x] Write protocol tests (139 new tests)
- [x] Implement DefaultActor
- [x] Implement DefaultPermissionChecker
- [x] Implement DefaultNamespaceResolver
- [x] Update AccessPolicy with new fields (owner, ACLs, session binding)
- [x] Export access control module from main `__init__.py`
- [x] All tests passing (249 total), 92% coverage

---

## References

- Current permissions: `src/mcp_refcache/permissions.py`
- Current cache: `src/mcp_refcache/cache.py`
- BundesMCP patterns: `.agent/files/tmp/session/`
- Project rules: `.rules`
