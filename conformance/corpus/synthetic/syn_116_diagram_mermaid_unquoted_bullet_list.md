# Diagram in Bullet List

* Subsystem Flowchart:

```mermaid
flowchart LR
    Start(Sensor Init\nSelf-Test) --> Check{Voltages Normal\nRail OK?}
    Check -->|Yes| Run[Operational\nTelemetry Active]
```

