// Owned, non-executable PE fixture; runs production AOB resolution and guards.
#define NOMINMAX
#include <Windows.h>
#include <fstream>
#include <iostream>
#include <vector>
#include "../../../../game/AOBScan.h"

int wmain(int argc,wchar_t**argv) {
    if(argc!=2)return 2;
    std::ifstream file(argv[1],std::ios::binary|std::ios::ate);if(!file)return 3;
    std::vector<unsigned char> raw(static_cast<size_t>(file.tellg()));file.seekg(0);file.read(reinterpret_cast<char*>(raw.data()),raw.size());
    if(!file||raw.size()<4096)return 4;
    auto dos=reinterpret_cast<const IMAGE_DOS_HEADER*>(raw.data());
    auto nt=reinterpret_cast<const IMAGE_NT_HEADERS64*>(raw.data()+dos->e_lfanew);
    if(nt->OptionalHeader.SizeOfImage>512*1024*1024)return 5;
    std::vector<unsigned char> image(nt->OptionalHeader.SizeOfImage);
    memcpy(image.data(),raw.data(),nt->OptionalHeader.SizeOfHeaders);
    auto section=IMAGE_FIRST_SECTION(nt);
    for(unsigned i=0;i<nt->FileHeader.NumberOfSections;++i){
        if(static_cast<size_t>(section[i].VirtualAddress)+section[i].SizeOfRawData>image.size()||
           static_cast<size_t>(section[i].PointerToRawData)+section[i].SizeOfRawData>raw.size())return 6;
        memcpy(image.data()+section[i].VirtualAddress,raw.data()+section[i].PointerToRawData,section[i].SizeOfRawData);
    }
    const uintptr_t base=reinterpret_cast<uintptr_t>(image.data());
    const auto hash=ExposerCompatibility::FileHash(argv[1]);
    const int version=ExposerCompatibility::Select(base,hash);
    if(!version||ExposerCompatibility::Select(base,std::string(64,'0')))return 7;
    ExposerCompatibility::Version.store(version);
    if(ExposerCompatibility::WorldField(0x1e648)!=(version==272?0x1e658:0x1e648))return 8;
    PROCESS_INFO.init=true;PROCESS_INFO.hProcess=GetCurrentProcess();PROCESS_INFO.hModule=reinterpret_cast<HMODULE>(base);
    PROCESS_INFO.mInfo.lpBaseOfDll=image.data();PROCESS_INFO.mInfo.SizeOfImage=static_cast<DWORD>(image.size());
    GetText();ScanAndAssignAddresses();
    if(registeredAddresses.size()!=21||!ExposerCompatibility::ValidateRegistered(base,registeredAddresses,version))return 9;
    const auto* bindings=version==272?ExposerBindings272:ExposerBindings271;
    unsigned negatives=0;
    for(size_t i=0;i<21;++i){
        for(auto& item:registeredAddresses)if(strcmp(item.first,bindings[i].name)==0){
            auto previous=item.second;item.second=reinterpret_cast<void*>(base+1);
            if(ExposerCompatibility::ValidateRegistered(base,registeredAddresses,version))return 10;
            item.second=previous;++negatives;
        }
        if(bindings[i].length){
            image[bindings[i].rva]^=1;
            if(ExposerCompatibility::ValidateRegistered(base,registeredAddresses,version))return 11;
            image[bindings[i].rva]^=1;++negatives;
        }
    }
    for(auto at:{static_cast<size_t>(dos->e_lfanew+8),static_cast<size_t>(version==272?0x506a15:0x5067e7),static_cast<size_t>(version==272?0x506a9a:0x50686e)}){
        image[at]^=1;if(ExposerCompatibility::Select(base,hash))return 12;image[at]^=1;++negatives;
    }
    std::cout<<"PASS Exposer WW"<<version<<": 21 production bindings; "<<negatives<<" corruptions rejected; no hooks/game execution\n";
    return 0;
}
