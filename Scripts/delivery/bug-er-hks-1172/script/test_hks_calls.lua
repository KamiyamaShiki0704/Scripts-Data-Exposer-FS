-- Only Lua call records are produced; env/act never access process memory.
local candidate = assert(arg[1], 'candidate script root required')
local installed = assert(arg[2], 'installed script root for unchanged helpers required')
unpack = table.unpack
TRUE, FALSE = 1, 0
GAME_BASE, CHR_INS_BASE, TARGET_CHR_INS_BASE = 0, 1, 2
UNSIGNED_BYTE, SIGNED_BYTE, UNSIGNED_SHORT, SIGNED_SHORT = 0, 1, 2, 3
UNSIGNED_INT, SIGNED_INT, FLOAT, BIT = 4, 5, 6, 7
WritePointerChain, TraversePointerChain = 10000, 10000
local calls = {}
function act(...) calls[#calls+1] = {...} end
function env(...) calls[#calls+1] = {...}; return 0 end
local assertions = 0
local function equal(a,b)
    assert(a == b, tostring(a)..' ~= '..tostring(b))
    assertions = assertions + 1
end
local function load(relative)
    local chunk = loadfile(candidate..'/'..relative)
    if not chunk then chunk = assert(loadfile(installed..'/'..relative)) end
    chunk()
end
local function last() return calls[#calls] end
load('Module/exposer/ExposerVariables.hks')
load('Module/exposer/GameBasePointers.hks')
local p = GAME_BASE_POINTERS
equal(p.GAME_DATA_MAN.PLAYER_GAME_INFO.MULTIPLAYER_SLOT[3], 0x3d64fb8)
equal(p.WORLD_CHR_MAN.LOCAL_PLAYER_CHR_INS[3], 0x1e508)
equal(p.WORLD_CHR_MAN.DEBUG_CHR_CREATOR.IS_SPAWN[3], 0x1e658)
equal(p.WORLD_CHR_MAN.CHR_CAM.CAMERA_TYPE[3], 0x1ecf0)
equal(p.WORLD_CHR_MAN.CHR_INS_LIST_BY_DISTANCE.START_PTR[3], 0x1f1e8)
equal(p.WORLD_CHR_MAN.CHR_INS_LIST_BY_DISTANCE.END_PTR[3], 0x1f1f0)
equal(p.WORLD_CHR_MAN.CHR_INS_LIST_BY_DISTANCE.CHR_INS(3)[4], 0x30)
GetPointerValue(p.WORLD_CHR_MAN.CHR_INS_LIST_BY_DISTANCE.END_PTR)
equal(last()[2], 3); equal(last()[4], 0x1f1f0)
SetPointerValue(p.WORLD_CHR_MAN.DEBUG_CHR_CREATOR.IS_SPAWN, 1)
equal(last()[4], 1); equal(last()[5], 0x1e658); equal(last()[6], 0x44)
equal(p.DEBUG_FLAGS.ALL_NO_ARROW_CONSUME[3], '0x3D6D236')
load('Module/MovementControl.lua')
SetWorldSpeedModifier(0.5)
equal(last()[1], 10000); equal(last()[2], 0); equal(last()[3], 6)
equal(last()[4], 0.5); equal(last()[5], 0x4590b78); equal(last()[6], 0x2cc)
SetChrDebugNoHit(TRUE)
equal(last()[5], 3); equal(last()[6], 0x530)
local previous = #calls
SetChrDebugNoHit(999)
equal(#calls, previous)
load('Module/EnemySummon.lua')
SetDebugChrRotation(1,2,3)
for i = #calls-2, #calls do equal(calls[i][5], 0x1e658) end
GetPlayerYawRotation()
equal(last()[2], 3); equal(last()[4], 0x1e508)
load('Module/LoadingScreens.hks')
GetCurrentLoadingScreenTable()
equal(last()[2], 0); equal(last()[4], 0x3d67f48)
LocalPlayerHandleAsParts()
equal(last()[4], 0x1e508)
print('PASS '..assertions..' assertions; recorded env/act only')
