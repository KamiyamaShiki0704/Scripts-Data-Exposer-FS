#pragma once
#include <Windows.h>
#include <bcrypt.h>
#include <atomic>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
#include "CompatibilityData.h"
#pragma comment(lib,"bcrypt.lib")

namespace ExposerCompatibility {
inline std::atomic<int> Version{0};
inline bool Read(uintptr_t address,void* output,size_t length) {
    __try {memcpy(output,reinterpret_cast<void*>(address),length);return true;}
    __except(EXCEPTION_EXECUTE_HANDLER) {return false;}
}
inline bool Equal(uintptr_t address,const unsigned char* expected,size_t length) {
    __try {return memcmp(reinterpret_cast<void*>(address),expected,length)==0;}
    __except(EXCEPTION_EXECUTE_HANDLER) {return false;}
}
inline std::string FileHash(const wchar_t* path) {
    std::ifstream file(path,std::ios::binary);if(!file)return {};
    BCRYPT_ALG_HANDLE algorithm{};BCRYPT_HASH_HANDLE hash{};DWORD length=0,returned=0;
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)return {};
    bool ok=BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&length),sizeof(length),&returned,0)>=0;
    std::vector<unsigned char> object(length),buffer(65536);
    ok=ok&&BCryptCreateHash(algorithm,&hash,object.data(),length,nullptr,0,0)>=0;
    while(ok&&file){file.read(reinterpret_cast<char*>(buffer.data()),buffer.size());if(file.gcount())ok=BCryptHashData(hash,buffer.data(),static_cast<ULONG>(file.gcount()),0)>=0;}
    unsigned char digest[32]{};
    if(ok)ok=file.eof()&&BCryptFinishHash(hash,digest,sizeof(digest),0)>=0;
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);
    if(!ok)return {};char hex[65]{};for(int i=0;i<32;++i)sprintf_s(hex+i*2,3,"%02x",digest[i]);return hex;
}
inline int Select(uintptr_t base,const std::string& hash) {
    IMAGE_DOS_HEADER dos{};IMAGE_NT_HEADERS64 nt{};
    if(!Read(base,&dos,sizeof(dos))||dos.e_magic!=IMAGE_DOS_SIGNATURE||dos.e_lfanew<0x40||dos.e_lfanew>0x1000||
       !Read(base+dos.e_lfanew,&nt,sizeof(nt))||nt.Signature!=IMAGE_NT_SIGNATURE||
       nt.FileHeader.Machine!=IMAGE_FILE_MACHINE_AMD64||nt.OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR64_MAGIC)return 0;
    const auto stamp=nt.FileHeader.TimeDateStamp,size=nt.OptionalHeader.SizeOfImage;
    if(hash=="d1a84083c6c7c7902162ff098f7d86812839aa6b3575959398857e539c488134"&&stamp==0x69e9c9b9&&size==0x5e09600)return 270;
    int version=0;
    if(hash=="1a3547101327f65d0c76da2f9190ac0aa66871ea42bae2aecc61e11a8b597891"&&stamp==0x6a96b418&&size==0x5e0da00&&nt.OptionalHeader.AddressOfEntryPoint==0x24fe160)version=271;
    if(hash=="f9118fea2cfd8fa3901e8060bfadb1552cb2471771ded8a5b662c4e298ffb328"&&stamp==0x6aabf7e7&&size==0x5dfd600&&nt.OptionalHeader.AddressOfEntryPoint==0x24ff890)version=272;
    if(!version)return 0;
    const unsigned char oldFirst[]={0x48,0x8b,0x8f,0x48,0xe6,0x01,0x00};
    const unsigned char oldSecond[]={0x48,0x8b,0xb7,0x48,0xe6,0x01,0x00};
    const unsigned char newFirst[]={0x48,0x8b,0x8f,0x58,0xe6,0x01,0x00};
    const unsigned char newSecond[]={0x48,0x8b,0xb7,0x58,0xe6,0x01,0x00};
    if(!Equal(base+(version==272?0x506a15:0x5067e7),version==272?newFirst:oldFirst,7)||
       !Equal(base+(version==272?0x506a9a:0x50686e),version==272?newSecond:oldSecond,7))return 0;
    return version;
}
inline bool Initialize(uintptr_t base) {
    std::vector<wchar_t> path(32768);const auto count=GetModuleFileNameW(nullptr,path.data(),static_cast<DWORD>(path.size()));
    if(!count||count>=path.size())return false;
    const int selected=Select(base,FileHash(path.data()));
    Version.store(selected,std::memory_order_release);return selected!=0;
}
inline uintptr_t WorldField(uintptr_t legacy) {
    if(Version.load(std::memory_order_acquire)!=272)return legacy;
    switch(legacy){case 0x1e648:return 0x1e658;case 0x1e6a8:return 0x1e6b8;case 0x1ece0:return 0x1ecf0;
        case 0x1f1b0:return 0x1f1c0;case 0x1f1d0:return 0x1f1e0;case 0x1f200:return 0x1f210;default:return legacy;}
}
template<class Addresses> bool ValidateRegistered(uintptr_t base,const Addresses& addresses,int version) {
    const auto* bindings=version==272?ExposerBindings272:ExposerBindings271;
    for(size_t i=0;i<21;++i){
        const auto& expected=bindings[i];bool found=false;
        for(const auto& entry:addresses)if(strcmp(entry.first,expected.name)==0){
            if(!entry.second)return false;
            if(version!=270&&(reinterpret_cast<uintptr_t>(entry.second)!=base+expected.rva||
               (expected.length&&!Equal(base+expected.rva,expected.bytes,expected.length))))return false;
            found=true;break;
        }
        if(!found)return false;
    }
    return true;
}
}
