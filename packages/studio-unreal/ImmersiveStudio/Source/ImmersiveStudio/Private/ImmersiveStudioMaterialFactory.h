#pragma once

#include "CoreMinimal.h"

class UMaterial;
class UMaterialInstanceConstant;
class UTexture2D;

class FImmersiveStudioMaterialFactory
{
public:
	static UMaterial* GetOrCreatePackedOrmMasterMaterial();
	static UMaterial* GetOrCreateBaseMasterMaterial();

	static UMaterialInstanceConstant* CreateInstanceForPbrGroup(
		const FString& DestinationPath,
		const FString& MaterialName,
		UTexture2D* Albedo,
		UTexture2D* Normal,
		UTexture2D* Orm);
};
