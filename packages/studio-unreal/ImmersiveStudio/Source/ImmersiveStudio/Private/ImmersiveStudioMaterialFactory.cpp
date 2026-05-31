#include "ImmersiveStudioMaterialFactory.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialExpression.h"
#include "Materials/MaterialExpressionComponentMask.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Materials/MaterialExpressionTextureSampleParameter.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Misc/PackageName.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"

namespace
{
	const TCHAR* PackedOrmMasterPath = TEXT("/ImmersiveStudio/Materials/M_StudioPackedORM.M_StudioPackedORM");
	const TCHAR* BaseMasterPath = TEXT("/ImmersiveStudio/Materials/M_StudioBase.M_StudioBase");

	UMaterial* LoadMaster(const TCHAR* ObjectPath)
	{
		return LoadObject<UMaterial>(nullptr, ObjectPath);
	}

	void ConnectExpression(FExpressionInput& Input, UMaterialExpression* Expression, int32 OutputIndex = 0)
	{
		Input.Expression = Expression;
		Input.OutputIndex = OutputIndex;
	}

	UMaterial* CreateMasterMaterial(
		const FString& AssetPath,
		const FName& AssetName,
		bool bIncludeOrm)
	{
		UPackage* Package = CreatePackage(*AssetPath);
		if (!Package)
		{
			return nullptr;
		}

		Package->FullyLoad();

		UMaterial* Material = NewObject<UMaterial>(Package, AssetName, RF_Public | RF_Standalone);
		if (!Material)
		{
			return nullptr;
		}

		Material->SetShadingModel(MSM_DefaultLit);
		UMaterialEditorOnlyData* EditorOnly = Material->GetEditorOnlyData();

		UMaterialExpressionTextureSampleParameter* BaseColorParam =
			NewObject<UMaterialExpressionTextureSampleParameter>(Material);
		BaseColorParam->ParameterName = TEXT("BaseColorMap");
		BaseColorParam->SamplerType = SAMPLERTYPE_Color;
		EditorOnly->ExpressionCollection.AddExpression(BaseColorParam);
		ConnectExpression(EditorOnly->BaseColor, BaseColorParam);

		UMaterialExpressionTextureSampleParameter* NormalParam =
			NewObject<UMaterialExpressionTextureSampleParameter>(Material);
		NormalParam->ParameterName = TEXT("NormalMap");
		NormalParam->SamplerType = SAMPLERTYPE_Normal;
		EditorOnly->ExpressionCollection.AddExpression(NormalParam);
		ConnectExpression(EditorOnly->Normal, NormalParam);

		if (bIncludeOrm)
		{
			UMaterialExpressionTextureSampleParameter* OrmParam =
				NewObject<UMaterialExpressionTextureSampleParameter>(Material);
			OrmParam->ParameterName = TEXT("ORMMap");
			OrmParam->SamplerType = SAMPLERTYPE_LinearColor;
			EditorOnly->ExpressionCollection.AddExpression(OrmParam);

			UMaterialExpressionComponentMask* OrmR = NewObject<UMaterialExpressionComponentMask>(Material);
			OrmR->R = true;
			ConnectExpression(OrmR->Input, OrmParam);
			EditorOnly->ExpressionCollection.AddExpression(OrmR);
			ConnectExpression(EditorOnly->AmbientOcclusion, OrmR);

			UMaterialExpressionComponentMask* OrmG = NewObject<UMaterialExpressionComponentMask>(Material);
			OrmG->G = true;
			ConnectExpression(OrmG->Input, OrmParam);
			EditorOnly->ExpressionCollection.AddExpression(OrmG);
			ConnectExpression(EditorOnly->Roughness, OrmG);

			UMaterialExpressionComponentMask* OrmB = NewObject<UMaterialExpressionComponentMask>(Material);
			OrmB->B = true;
			ConnectExpression(OrmB->Input, OrmParam);
			EditorOnly->ExpressionCollection.AddExpression(OrmB);
			ConnectExpression(EditorOnly->Metallic, OrmB);
		}
		else
		{
			UMaterialExpressionConstant* RoughnessDefault = NewObject<UMaterialExpressionConstant>(Material);
			RoughnessDefault->R = 0.5f;
			EditorOnly->ExpressionCollection.AddExpression(RoughnessDefault);
			ConnectExpression(EditorOnly->Roughness, RoughnessDefault);

			UMaterialExpressionConstant* MetallicDefault = NewObject<UMaterialExpressionConstant>(Material);
			MetallicDefault->R = 0.f;
			EditorOnly->ExpressionCollection.AddExpression(MetallicDefault);
			ConnectExpression(EditorOnly->Metallic, MetallicDefault);
		}

		Material->PreEditChange(nullptr);
		Material->PostEditChange();

		FAssetRegistryModule::AssetCreated(Material);
		Package->MarkPackageDirty();

		FSavePackageArgs SaveArgs;
		SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
		const FString PackageFileName = FPackageName::LongPackageNameToFilename(
			AssetPath,
			FPackageName::GetAssetPackageExtension());
		UPackage::SavePackage(Package, Material, *PackageFileName, SaveArgs);

		return Material;
	}
}

UMaterial* FImmersiveStudioMaterialFactory::GetOrCreatePackedOrmMasterMaterial()
{
	if (UMaterial* Existing = LoadMaster(PackedOrmMasterPath))
	{
		return Existing;
	}

	return CreateMasterMaterial(
		TEXT("/ImmersiveStudio/Materials/M_StudioPackedORM"),
		TEXT("M_StudioPackedORM"),
		true);
}

UMaterial* FImmersiveStudioMaterialFactory::GetOrCreateBaseMasterMaterial()
{
	if (UMaterial* Existing = LoadMaster(BaseMasterPath))
	{
		return Existing;
	}

	return CreateMasterMaterial(
		TEXT("/ImmersiveStudio/Materials/M_StudioBase"),
		TEXT("M_StudioBase"),
		false);
}

UMaterialInstanceConstant* FImmersiveStudioMaterialFactory::CreateInstanceForPbrGroup(
	const FString& DestinationPath,
	const FString& MaterialName,
	UTexture2D* Albedo,
	UTexture2D* Normal,
	UTexture2D* Orm)
{
	if (!Albedo)
	{
		return nullptr;
	}

	UMaterial* Parent = Orm ? GetOrCreatePackedOrmMasterMaterial() : GetOrCreateBaseMasterMaterial();
	if (!Parent)
	{
		return nullptr;
	}

	const FString PackagePath = DestinationPath / MaterialName;
	UPackage* Package = CreatePackage(*PackagePath);
	if (!Package)
	{
		return nullptr;
	}

	Package->FullyLoad();

	UMaterialInstanceConstant* Instance = NewObject<UMaterialInstanceConstant>(
		Package,
		*MaterialName,
		RF_Public | RF_Standalone);
	if (!Instance)
	{
		return nullptr;
	}

	Instance->SetParentEditorOnly(Parent);
	Instance->SetTextureParameterValueEditorOnly(TEXT("BaseColorMap"), Albedo);

	if (Normal)
	{
		Instance->SetTextureParameterValueEditorOnly(TEXT("NormalMap"), Normal);
	}

	if (Orm)
	{
		Instance->SetTextureParameterValueEditorOnly(TEXT("ORMMap"), Orm);
	}

	Instance->PreEditChange(nullptr);
	Instance->PostEditChange();

	FAssetRegistryModule::AssetCreated(Instance);
	Package->MarkPackageDirty();

	FSavePackageArgs SaveArgs;
	SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
	const FString PackageFileName = FPackageName::LongPackageNameToFilename(
		PackagePath,
		FPackageName::GetAssetPackageExtension());
	UPackage::SavePackage(Package, Instance, *PackageFileName, SaveArgs);

	return Instance;
}
