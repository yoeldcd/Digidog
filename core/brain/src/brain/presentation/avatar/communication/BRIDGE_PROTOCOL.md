<!-- Author: Yoel David <yoeldcd@gmail.com> | X: https://x.com/SAY6267 -->

# Payload-blind avatar bridge protocol

The native bridge transports references, never avatar message bodies.

## Producer contract

The avatar persists the complete reply and publishes an opaque `message_id`.
Repeated writes with the same UUID are idempotent.

## Bridge contract

`avatar-outbox claim --json` may expose only:

- `message_id`
- `thread_id`
- `host_id`
- `created_at`
- the lease token required for acknowledgement or release

The bridge must not invoke `resolve-avatar-message`, query message storage directly, or
deduplicate by content. It reconciles deliveries using `message_id` only.

The complete prompt relayed to the destination task is one command:

```powershell
py '$agent/scripts/brain.py' resolve-avatar-message read MESSAGE_ID --json
```

## Consumer contract

The destination task runs the relayed command. `resolve-avatar-message read` resolves
the body by UUID and records consumption in the same operation. An unknown or
invalid UUID fails without revealing another message.

## Delivery states

1. `pending`: the producer stored a message and its reference awaits transport.
2. `leased`: a bridge worker temporarily owns the opaque reference.
3. `delivered`: Codex accepted the read command for the destination task.
4. `consumed`: the destination resolved the body by UUID.

The bridge acknowledges delivery only after native send succeeds. A failed
transport releases the lease or lets it expire; it never reads the payload to
reconcile the result.
