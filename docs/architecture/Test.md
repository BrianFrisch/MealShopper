```mermaid
graph TB
    %% Styling and Definitions
    classDef filestore fill:#999,stroke:#000,color:#fff;
    PlannerFileStoreClass(["Planner Data<br>Data"]):::filestore;
    PlannerFileStore@{ shape: lin-cyl, label: "Datastore" };
    style PlannerFileStore fill:#fff,stroke:#000,color:#000;

    PlannerRdbms[("Planner Cache<br>RDBMS")]:::database
    PlannerCache[("Planner Cache<br>Redis")]:::cache
    PlannerCache --> PlannerFileStore
    classDef database fill:#fdd208,stroke:#000000,color:#000;
    classDef cache fill:#d93327,stroke:#000,color:#fff;
