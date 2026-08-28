#pragma once

#include <Windows.h>
#include <Xinput.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <mutex>
#include <unordered_map>

#pragma comment(lib, "Xinput.lib")

namespace InputState
{
using Clock = std::chrono::steady_clock;

enum class Device : int
{
    Keyboard = 0,
    XInputButton = 1,
    XInputTrigger = 2,
};

enum class Trigger : int
{
    Left = 0,
    Right = 1,
};

inline constexpr BYTE TRIGGER_THRESHOLD = 30;
inline constexpr int XINPUT_STANDARD_BUTTON_MASK =
    XINPUT_GAMEPAD_DPAD_UP
    | XINPUT_GAMEPAD_DPAD_DOWN
    | XINPUT_GAMEPAD_DPAD_LEFT
    | XINPUT_GAMEPAD_DPAD_RIGHT
    | XINPUT_GAMEPAD_START
    | XINPUT_GAMEPAD_BACK
    | XINPUT_GAMEPAD_LEFT_THUMB
    | XINPUT_GAMEPAD_RIGHT_THUMB
    | XINPUT_GAMEPAD_LEFT_SHOULDER
    | XINPUT_GAMEPAD_RIGHT_SHOULDER
    | XINPUT_GAMEPAD_A
    | XINPUT_GAMEPAD_B
    | XINPUT_GAMEPAD_X
    | XINPUT_GAMEPAD_Y;

class HoldTracker
{
public:
    float update(bool down, Clock::time_point now)
    {
        if (!down)
        {
            down_ = false;
            return 0.0f;
        }

        if (!down_)
        {
            down_ = true;
            startedAt_ = now;
            return 1.0f;
        }

        const float elapsedMilliseconds =
            std::chrono::duration<float, std::milli>(now - startedAt_).count();
        return (std::max)(1.0f, elapsedMilliseconds);
    }

private:
    bool down_ = false;
    Clock::time_point startedAt_{};
};

inline bool isInputCodeValid(int device, int code)
{
    switch (static_cast<Device>(device))
    {
    case Device::Keyboard:
        return code >= 0x01 && code <= 0xFE;
    case Device::XInputButton:
        return code > 0
            && (code & ~XINPUT_STANDARD_BUTTON_MASK) == 0;
    case Device::XInputTrigger:
        return code == static_cast<int>(Trigger::Left)
            || code == static_cast<int>(Trigger::Right);
    }

    return false;
}

inline bool isGameFocused()
{
    const HWND foregroundWindow = GetForegroundWindow();
    if (foregroundWindow == nullptr)
        return false;

    DWORD foregroundProcessId = 0;
    GetWindowThreadProcessId(foregroundWindow, &foregroundProcessId);
    return foregroundProcessId == GetCurrentProcessId();
}

inline bool isXInputButtonDown(const XINPUT_GAMEPAD& gamepad, int code)
{
    if (!isInputCodeValid(static_cast<int>(Device::XInputButton), code))
        return false;

    const WORD buttonMask = static_cast<WORD>(code);
    return (gamepad.wButtons & buttonMask) == buttonMask;
}

inline bool isXInputTriggerDown(const XINPUT_GAMEPAD& gamepad, int code)
{
    if (code == static_cast<int>(Trigger::Left))
        return gamepad.bLeftTrigger > TRIGGER_THRESHOLD;
    if (code == static_cast<int>(Trigger::Right))
        return gamepad.bRightTrigger > TRIGGER_THRESHOLD;
    return false;
}

inline bool isInputDown(int device, int code)
{
    if (!isInputCodeValid(device, code) || !isGameFocused())
        return false;

    switch (static_cast<Device>(device))
    {
    case Device::Keyboard:
        return (GetAsyncKeyState(code) & 0x8000) != 0;
    case Device::XInputButton:
    case Device::XInputTrigger:
    {
        XINPUT_STATE state{};
        if (XInputGetState(0, &state) != ERROR_SUCCESS)
            return false;

        if (static_cast<Device>(device) == Device::XInputButton)
            return isXInputButtonDown(state.Gamepad, code);
        return isXInputTriggerDown(state.Gamepad, code);
    }
    }

    return false;
}

inline std::uint32_t inputTrackerKey(int device, int code)
{
    return (static_cast<std::uint32_t>(device) << 16)
        | static_cast<std::uint16_t>(code);
}

inline float inputDurationMilliseconds(int device, int code)
{
    if (!isInputCodeValid(device, code))
        return 0.0f;

    const bool down = isInputDown(device, code);
    const Clock::time_point now = Clock::now();

    static std::mutex trackerMutex;
    static std::unordered_map<std::uint32_t, HoldTracker> trackers;
    const std::lock_guard<std::mutex> lock(trackerMutex);
    return trackers[inputTrackerKey(device, code)].update(down, now);
}
}
