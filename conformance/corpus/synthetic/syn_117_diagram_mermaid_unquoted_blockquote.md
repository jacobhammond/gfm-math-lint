# Diagram in Blockquote

> Subsystem Flowchart:

```mermaid
flowchart LR
    Start(Sensor Init\nSelf-Test) --> Check{Voltages Normal\nRail OK?}
    Check -->|Yes| Run[Operational\nTelemetry Active]
```

