#pragma once

#include "CoreMinimal.h"

struct FImmersiveStudioMaterialSlot
{
	FString Id;
	FString Role;
};

struct FImmersiveStudioVariant
{
	FString VariantId;
	FString Label;
};

struct FImmersiveStudioUnityHints
{
	FString ImportSubfolder;
	FString Collider;
};

struct FImmersiveStudioAssetSpec
{
	FString AssetId;
	FString DisplayName;
	float TargetHeightM = 1.f;
	TArray<FImmersiveStudioMaterialSlot> MaterialSlots;
	TArray<FImmersiveStudioVariant> Variants;
	FImmersiveStudioUnityHints Unity;
};

struct FImmersiveStudioJobManifest
{
	FString JobId;
	TArray<FImmersiveStudioAssetSpec> Assets;
};

class FImmersiveStudioManifestParser
{
public:
	static bool ParseFromFile(const FString& ManifestPath, FImmersiveStudioJobManifest& OutManifest, FString& OutError);
};
