# Project Architecture Diagrams

## 1. High-Level Block Diagram - System Components

```mermaid
graph LR
    subgraph "Input Layer"
        Audio[Audio Files<br/>Stereo WAV]
        Config[Configuration<br/>Credentials<br/>Phone Numbers<br/>Agent Details]
    end

    subgraph "Processing Layer"
        Python[Python Application<br/><br/>• Audio Splitting<br/>• S3 Upload<br/>• Browser Automation<br/>• Call Orchestration]
    end

    subgraph "Cloud Services"
        S3Bucket[AWS S3<br/>liamfrawley<br/>eu-north-1<br/><br/>Customer Audio<br/>Storage]

        TwilioSvc[Twilio<br/><br/>• Call Initiation<br/>• TwiML Execution<br/>• Audio Playback]

        WxCCDesktop[Webex Contact Center<br/>Agent Desktop<br/><br/>• Agent Login<br/>• Call Routing<br/>• Call Handling]
    end

    subgraph "Output Layer"
        Demo[Demo Call<br/>Simulation<br/><br/>Recorded Customer + Agent<br/>Conversation]
    end

    %% Flow connections
    Audio --> Python
    Config --> Python

    Python --> |Upload<br/>Customer Audio| S3Bucket
    Python --> |Create Call<br/>TwiML URL| TwilioSvc
    Python --> |Automate Agent<br/>Playwright| WxCCDesktop

    S3Bucket --> |Fetch Audio| TwilioSvc
    TwilioSvc --> |Dial In<br/>Play Audio| WxCCDesktop

    WxCCDesktop --> Demo

    style Python fill:#e1f5ff
    style TwilioSvc fill:#ff6b6b
    style S3Bucket fill:#ffd93d
    style WxCCDesktop fill:#6bcf7f
    style Demo fill:#a29bfe
```

### Audio Splitting Process Detail

```mermaid
graph TB
    subgraph "Input"
        Stereo[Stereo WAV File<br/>audio/recording.wav<br/><br/>Left Channel: Customer<br/>Right Channel: Agent]
    end

    subgraph "Audio Processing - stereoSplitter.py"
        FFmpeg[FFmpeg Processing]
        PanLeft["pan=mono|c0=c0<br/>(Extract Left Channel)"]
        PanRight["pan=mono|c0=c1<br/>(Extract Right Channel)"]
    end

    subgraph "Output Files"
        Customer[Customer Audio<br/>recording_customer.wav<br/><br/>Mono - Left Channel Only]
        Agent[Agent Audio<br/>recording_agent.wav<br/><br/>Mono - Right Channel Only]
    end

    subgraph "Destinations"
        S3Upload[Upload to S3<br/>→ Twilio plays to WxCC]
        BrowserMic[Inject as Microphone<br/>→ Playwright browser input]
    end

    Stereo --> FFmpeg
    FFmpeg --> PanLeft
    FFmpeg --> PanRight
    PanLeft --> Customer
    PanRight --> Agent

    Customer --> S3Upload
    Agent --> BrowserMic

    style Stereo fill:#e8f4f8
    style Customer fill:#ffd93d
    style Agent fill:#a29bfe
    style S3Upload fill:#ffd93d
    style BrowserMic fill:#6bcf7f
```

**Audio Split Details:**

- **Input Format**: Stereo WAV file (2 channels)
- **Left Channel**: Customer audio → uploaded to S3 → played by Twilio
- **Right Channel**: Agent audio → injected into browser → used as microphone input
- **Processing**: FFmpeg with pan filter extracts each channel independently
- **Output Format**: Two mono WAV files (PCM 16-bit, 16kHz typical)

## 2. Sequence Diagram - Call Flow

```mermaid
sequenceDiagram
    participant Main as main.py
    participant Audio as Audio Processor
    participant S3 as AWS S3
    participant Agent as Fake Agent
    participant WxCC as Webex Contact Center
    participant Twilio as Twilio Service

    Main->>Main: Load config.json
    Main->>Audio: Split stereo WAV file
    Audio-->>Main: customer_audio.wav, agent_audio.wav

    Main->>S3: Upload customer_audio.wav
    S3-->>Main: Public URL

    Main->>Agent: Launch browser (Playwright)
    Agent->>WxCC: Navigate to Agent Desktop
    Agent->>WxCC: Login with credentials
    Agent->>Agent: Inject agent_audio.wav as mic input
    Agent->>WxCC: Set availability to "Available"

    par Wait for Agent Ready
        Agent->>Main: Signal ready for call
    and Initiate Call
        Main->>Twilio: Create call with TwiML
        Note over Twilio: TwiML includes:<br/>- Pause (0.8s)<br/>- Play customer audio URL
    end

    Twilio->>WxCC: Dial contact center number
    WxCC->>Agent: Route call to available agent

    Agent->>WxCC: Detect incoming call (md-task-item)
    Agent->>WxCC: Press Enter to answer

    par Audio Playback
        Twilio->>WxCC: Stream customer audio (from S3)
    and Agent Response
        Agent->>WxCC: Stream agent audio (from local file)
    end

    Note over Agent,WxCC: Call conversation in progress

    Main->>Main: Wait for call duration
    Main->>Agent: Signal to end call
    Agent->>WxCC: End call

    Main->>Agent: Close browser (if configured)
    Main->>Main: Process next audio file (if any)
```

## Component Descriptions

### Python Application Components

- **main.py**: Core orchestrator that coordinates the entire workflow
- **Audio Processor**: Splits stereo recordings into separate customer and agent channels
- **S3 Upload Manager**: Handles uploading customer audio to AWS S3 with public-read permissions
- **Fake Agent Module**: Browser automation using Playwright to simulate agent behavior
  - Logs into WxCC Agent Desktop
  - Sets availability status
  - Answers incoming calls
  - Injects pre-recorded agent audio as microphone input
- **Twilio Integration**: Creates and monitors calls via Twilio REST API

### External Services

- **Twilio**: Telephony service that initiates calls and plays customer audio
- **AWS S3**: Storage for customer audio files (publicly accessible URLs)
- **Webex Contact Center (WxCC)**: Target contact center system where demo calls are routed

### Key Features

1. **Multi-Agent Support**: Can run multiple agents with different credentials and audio files
2. **Automated Audio Processing**: Automatically splits stereo files into customer/agent channels
3. **Configurable Timing**: Adjustable delay before customer audio playback
4. **Browser Automation**: Uses Playwright for realistic agent simulation
5. **S3 Integration**: Uploads audio to S3 for Twilio access

```

## Technology Stack

- **Python 3.x** - Core application language
- **Playwright** - Browser automation for agent simulation
- **Twilio API** - Telephony and call management
- **AWS Boto3** - S3 integration for audio storage
- **FFmpeg** - Audio processing and channel splitting
- **Webex Contact Center** - Target demo system
```
