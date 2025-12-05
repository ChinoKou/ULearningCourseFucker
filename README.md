# ULearningCWAuto

## What is ULearningCWAuto?

ULearningCWAuto is an automated CLI tool for completing courseware on the ULearning platform.

## Features

- Video watching with simulated progress
- Question answering with automatic solution lookup
- Document reading simulation
- Content page completion
- Customizable study time
- Multiple users support
- Modify courseware configuration

## Support Sites

- [ULearning](https://www.ulearning.cn)
- [DGUT](https://lms.dgut.edu.cn)

## Usage

- Download the latest release binary from the releases page and run it directly
- Clone the repository and run with Python 3.12+ directly

## How It Works

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Main as CLI Main
    participant CM as CourseManager
    participant DM as DataManager
    participant API as CourseAPI
    participant Server as ULearning Server

    User->>Main: Select "Start Courseware"
    Main->>CM: Invoke __start_course_ware()
    activate CM
    
    Note over CM: Load UserConfig<br/>Iterate: Course -> Textbook -> Chapter -> Section

    loop Every "Section"
        CM->>API: initialize_section(section_id)
        activate API
        API->>Server: GET /studyrecord/initialize/{id}
        Server-->>API: Return timestamp (studyStartTime)
        API-->>CM: Return timestamp
        deactivate API

        loop Every "Page" in Section
            alt Page Type is Video
                loop Every Video Element
                    CM->>API: watch_video_behavior(video_id...)
                    API->>Server: POST /behavior/watchVideo
                    Note right of API: Send video heartbeat/anti-cheat beacon
                end
            end
            Note over CM: Simulate study duration<br/>(Sleep / Random Delay)
        end

        CM->>DM: build_sync_study_record_request()
        activate DM
        Note right of DM: 1. Calculate total study time<br/>2. Generate video progress data<br/>3. Fill in correct answers<br/>4. Randomize operation times
        DM-->>CM: Return SyncStudyRecordAPIRequest object
        deactivate DM

        CM->>API: sync_study_record(request_data)
        activate API
        Note right of API: Call utils.sync_text_encrypt<br/>Encrypt payload (DES + Base64)
        API->>Server: POST /yws/api/personal/sync
        Server-->>API: Return Status "1" (Success)
        API-->>CM: Return True
        deactivate API

        Note over CM: Cooling down (Sleep Time)
    end

    CM-->>Main: All Tasks Completed
    Main-->>User: Show Success Message
    deactivate CM
```

## Terms and Conditions

By using this tool, you acknowledge that you understand the risks associated with using automation tools on ULearning platforms, and accept the following terms and conditions:

- The author does not guarantee that using this tool will not be detected by the ULearning platform
- Any consequences arising from the use of this tool, including but not limited to disciplinary action, are solely the responsibility of the user
