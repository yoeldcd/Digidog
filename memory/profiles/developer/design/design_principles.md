# Architectural Applicable Principles

* To isolate changes and prevent side effects, ensure every module, class, function, and service owns exactly one coherent reason to change — apply **Single Responsibility Principle**.
* To support future extensions without modifying existing code, introduce stable extension contracts instead of adding conditionals to central routines or composition roots — apply **Open/Closed Principle**.
* To guarantee that implementations can be swapped safely without breaking callers, preserve all behavioral promises, inputs, outputs, invariants, and failure semantics of the base abstraction — apply **Liskov Substitution Principle**.
* To avoid forcing components to depend on unused capabilities, design narrow, client-focused ports instead of broad god interfaces or shared toolkit bundles — apply **Interface Segregation Principle**.
* To decouple high-level domain policies from infrastructure details, depend on abstractions and injected ports while keeping presentation and persistence adapters facing inward — apply **Dependency Inversion Principle**.
* To place logic where data naturally resides, assign responsibilities directly to the object or module that holds the state required to perform them — apply **Information Expert**.
* To make object creation coherent and maintainable, assign instantiation responsibility where aggregation, lifecycle ownership, initialization context, or frequent use makes creation natural — apply **Creator**.
* To isolate system event handling from domain logic and rendering, define one explicit application boundary that receives and coordinates events without absorbing domain rules or UI work — apply **Controller**.
* To minimize ripple effects when code evolves, reduce knowledge of concrete collaborators and eliminate bidirectional, cyclic, hidden, or toolkit-crossing dependencies — apply **Low Coupling**.
* To keep related code focused and easy to reason about, group strongly related behavior into unified identities and exclude responsibilities that evolve for different reasons — apply **High Cohesion**.
* To handle behavioral variations cleanly without nested conditionals, introduce substitutable strategy implementations when stable variations exist rather than branching on type flags — apply **Polymorphism**.
* To maintain high cohesion when no domain concept fits a responsibility, introduce an artificial service class or module that cleanly owns the responsibility — apply **Pure Fabrication**.
* To decouple two collaborating components, introduce an intermediate port, adapter, or service boundary only when it materially reduces direct dependency knowledge — apply **Indirection**.
* To shield application logic from unstable third-party APIs or infrastructure changes, wrap unstable details, toolkits, engines, persistence, and external schemas behind stable interface contracts — apply **Protected Variations**.

These last nine principles are the **General Responsibility Assignment Software Patterns** responsibility-design patterns; they MUST be referenced by their full names in plans and reviews, not only by an acronym.

Compliance is not proven by small files, passing tests, or added interfaces alone. Before mutable work, the plan or atomic-change rationale MUST map responsibilities and dependency direction to the applicable guidance and named principles. Every worker assignment MUST receive the relevant architectural constraints. Before integration, @Angi MUST inspect the resulting module identities, imports, ownership, substitution contracts, and extension points; validation MUST include architecture-specific evidence alongside behavioral tests. If the guidance is missing, contradictory, or the proposed change would violate it, stop before implementation and ask Yoi to approve a documented exception or revised architecture.
