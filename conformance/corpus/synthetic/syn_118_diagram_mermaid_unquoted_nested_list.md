# Diagram in Nested List

1. Sequence:
   1. Stage:

```mermaid
flowchart LR
    Start(Sensor Init\nSelf-Test) --> Check{Voltages Normal\nRail OK?}
    Check -->|Yes| Run[Operational\nTelemetry Active]
```

