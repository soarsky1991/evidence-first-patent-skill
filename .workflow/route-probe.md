# Model route probe

Probe timestamp: `2026-07-21T21:48:38-07:00` (`America/Los_Angeles`)

The same read-only prompt was sent independently to every requested route. The expected semantic response was `measured-is-not-designed`.

| Role | Requested model | Requested effort | Resolved model | Resolved effort | Exit | Output SHA-256 | Result |
|---|---|---|---|---|---:|---|---|
| Architecture | `gpt-5.6-sol` | `xhigh` | `gpt-5.6-sol` | `xhigh` | 0 | `e1f3af5637417bc84695b7b642e2ff53266e9e6dc598ddfa6fd261752f7b92f3` | PASS |
| Engineering | `gpt-5.6-terra` | `high` | `gpt-5.6-terra` | `high` | 0 | `e1f3af5637417bc84695b7b642e2ff53266e9e6dc598ddfa6fd261752f7b92f3` | PASS |
| Content | `gpt-5.6-luna` | `medium` | `gpt-5.6-luna` | `medium` | 0 | `e1f3af5637417bc84695b7b642e2ff53266e9e6dc598ddfa6fd261752f7b92f3` | PASS |

The digest is over the exact UTF-8 semantic response without a trailing newline. Runtime logs also contained non-blocking local state-database and optional-plugin synchronization warnings. Those warnings did not change the reported model, provider, sandbox, effort, response, or exit status.
