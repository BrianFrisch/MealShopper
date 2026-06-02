```mermaid
graph TB
    %% Styling and Definitions
    classDef boundary fill:none,stroke:#777,stroke-width:2px,stroke-dasharray: 5 5;
    classDef external fill:#999,stroke:#666,color:#fff,font-weight:bold;
    classDef container fill:#438dd5,stroke:#3b7aa3,color:#fff;
    classDef database fill:#fdd208,stroke:#000000,color:#000;
    classDef cache fill:#d93327,stroke:#000,color:#fff;
    
    %% Elements
    User@{shape: circle, label:"User"};
    style User fill:#fff
    
    subgraph Boundary_System [MealShopper System]
        UI["MealShopper UI<br>(Web/Mobile)"]:::container
        APIGateway["API Gateway"]:::container
        Orchestrator["Orchestrator Service<br>(State Machine/Workflow Manager)"]:::container

        %% Shopping Subgraph
        subgraph Boundary_Shopping [Shopping]
            ShopperDomain["Shopper Domain Service"]:::container
            StoreDiscovery@{shape: subproc, label:"Store Discovery Service"}
            style StoreDiscovery fill:#438DD5, color:#fff, stroke:#000
            LocationsDB[("Locations<br>RDBMS")]:::database
            StoreAdIngestion@{shape: subproc, label:"Store Ad Ingestion Service"}
            style StoreAdIngestion fill:#438DD5, color:#fff, stroke:#000
            FlyersStore@{shape: docs, label:"Flyers<br>Document Store"}
            style FlyersStore fill:#FFBF00, color:#000, stroke:#000
            StoreDealFinder@{shape: subproc, label:"Store Deal Finder Service"}
            style StoreDealFinder fill:#438DD5, color:#fff, stroke:#000
            DealsStore@{shape: docs, label"Deals<br>Document Store"}
            style DealsStore fill:#FFBF00, color:#000, stroke:#000
            DealFinderCache[("Deal Finder Cache<br>Pinecone")]:::cache
            DealEvalLLM@{shape: lin-rect, label: "Deal Evaluation LLM"}
            style DealEvalLLM fill:#E6E6FA, stroke:#000, color:#000
        end
        style Boundary_Shopping fill:#fff, stroke:#000

        %% Planning Subgraph
        subgraph Boundary_Planning [Planning]
            PlanningDomain["Planning Domain Service"]:::container
            MealPlanning@{shape: subproc, label: "Meal Planning Service"}
            style MealPlanning fill:#438DD5, color:#fff, stroke:#000
            DietaryValidation@{shape: subproc, label:"Dietary Validation Service"}
            style DietaryValidation fill:#438DD5, color:#fff, stroke:#000
            PlannerCache[("Planner Cache<br>Redis")]:::cache
            MealPlanLLM@{shape: lin-rect, label:"Meal Plan Generation LLM"};
            style MealPlanLLM fill:#E6E6FA, stroke:#000, color:#000
        end
        style Boundary_Planning fill:#fff, stroke:#000

        %% User Subgraph
        subgraph Boundary_User [User]
            UserService["User Service"]:::container
            UsersDB[("Users Data<br>(RDBMS")]:::database
        end
        style Boundary_User fill:#fff, stroke:#000


        %% Utility Subgraph
        subgraph Boundary_Utility [Utility]
            SecurityService["Security Service"]:::container
            PIIEncryption["PII Encryption Service"]:::container
            KMS@{shape: lin-rect, label: "KMS"};
            style KMS fill:#999, color:#fff, stroke:#000
            IdentityProvider@{shape: lin-rect, label: "Identity Provider<br>(OAuth2)"}
            style IdentityProvider fill:#999, color:#fff, stroke:#000
        end
        style Boundary_Utility fill:#fff, stroke:#000

    end
    style Boundary_System fill:#fff

    %% External Services
    MappingService@{ shape: cloud, label: "Google Maps" }
    style MappingService fill:#fff, stroke:#000, color:#000;

    %% Relationships and Flows
    User --> UI
    UI --> APIGateway
    APIGateway --> Orchestrator

    %% Shopping Flows
    %%Orchestrator --> StoreDiscovery
    Orchestrator --> ShopperDomain
    ShopperDomain --> StoreDiscovery
    StoreDiscovery --> LocationsDB
    StoreDiscovery -- "If empty areas need searching" --> MappingService
    %%MappingService -- "Finds stores & stores them" --> LocationsDB
    ShopperDomain --> StoreAdIngestion
    StoreAdIngestion -- "Stores flyers locally & parses" --> FlyersStore
    StoreAdIngestion -- "Writes deals" --> DealsStore
    ShopperDomain --> StoreDealFinder
    StoreDealFinder -- "Read-only interface" --> DealsStore
    StoreDealFinder --> DealFinderCache
    StoreDealFinder --> DealEvalLLM
    
    %% Planning Flows
    Orchestrator --> PlanningDomain
    PlanningDomain --> DietaryValidation
    PlanningDomain --> MealPlanning
    MealPlanning --> PlannerCache
    MealPlanning --> MealPlanLLM
    %%DealEvalLLM -- "Assesses & identifies best deals" --> StoreDealFinder
    

    %% Utility Flows
    Orchestrator --> UserService
    UserService --> UsersDB
    UserService --> PIIEncryption
    
    %% Utility Flows
    PIIEncryption --> KMS
    SecurityService --> IdentityProvider