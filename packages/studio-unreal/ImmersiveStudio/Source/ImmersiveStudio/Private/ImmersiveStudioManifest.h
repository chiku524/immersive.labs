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

struct FImmersiveStudioUnrealHints
{
	FString ImportSubfolder;
	FString CollisionComplexity;
};

struct FImmersiveStudioAssetSpec
{
	FString AssetId;
	FString DisplayName;
	float TargetHeightM = 1.f;
	TArray<FImmersiveStudioMaterialSlot> MaterialSlots;
	TArray<FImmersiveStudioVariant> Variants;
	FImmersiveStudioUnityHints Unity;
	FImmersiveStudioUnrealHints Unreal;

	/** Effective Unreal collision complexity, falling back to the Unity collider mapping. */
	FString ResolveCollisionComplexity() const
	{
		if (!Unreal.CollisionComplexity.IsEmpty())
		{
			return Unreal.CollisionComplexity.ToLower();
		}

		const FString Collider = Unity.Collider.ToLower();
		if (Collider == TEXT("mesh_convex"))
		{
			return TEXT("convex");
		}
		if (Collider == TEXT("none"))
		{
			return TEXT("none");
		}
		return TEXT("simple");
	}
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
