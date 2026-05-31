#include "ImmersiveStudioManifest.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	bool ParseMaterialSlots(const TArray<TSharedPtr<FJsonValue>>* JsonArray, TArray<FImmersiveStudioMaterialSlot>& OutSlots)
	{
		if (!JsonArray)
		{
			return true;
		}

		for (const TSharedPtr<FJsonValue>& Value : *JsonArray)
		{
			const TSharedPtr<FJsonObject>* SlotObj = nullptr;
			if (!Value.IsValid() || !Value->TryGetObject(SlotObj) || !SlotObj->IsValid())
			{
				continue;
			}

			FImmersiveStudioMaterialSlot Slot;
			(*SlotObj)->TryGetStringField(TEXT("id"), Slot.Id);
			(*SlotObj)->TryGetStringField(TEXT("role"), Slot.Role);
			if (!Slot.Id.IsEmpty())
			{
				OutSlots.Add(MoveTemp(Slot));
			}
		}

		return true;
	}

	bool ParseVariants(const TArray<TSharedPtr<FJsonValue>>* JsonArray, TArray<FImmersiveStudioVariant>& OutVariants)
	{
		if (!JsonArray)
		{
			return true;
		}

		for (const TSharedPtr<FJsonValue>& Value : *JsonArray)
		{
			const TSharedPtr<FJsonObject>* VariantObj = nullptr;
			if (!Value.IsValid() || !Value->TryGetObject(VariantObj) || !VariantObj->IsValid())
			{
				continue;
			}

			FImmersiveStudioVariant Variant;
			(*VariantObj)->TryGetStringField(TEXT("variant_id"), Variant.VariantId);
			(*VariantObj)->TryGetStringField(TEXT("label"), Variant.Label);
			if (!Variant.VariantId.IsEmpty())
			{
				OutVariants.Add(MoveTemp(Variant));
			}
		}

		return true;
	}

	bool ParseUnityHints(const TSharedPtr<FJsonObject>& UnityObj, FImmersiveStudioUnityHints& OutHints)
	{
		if (!UnityObj.IsValid())
		{
			return true;
		}

		UnityObj->TryGetStringField(TEXT("import_subfolder"), OutHints.ImportSubfolder);
		UnityObj->TryGetStringField(TEXT("collider"), OutHints.Collider);
		return true;
	}

	bool ParseAsset(const TSharedPtr<FJsonObject>& AssetObj, FImmersiveStudioAssetSpec& OutAsset)
	{
		AssetObj->TryGetStringField(TEXT("asset_id"), OutAsset.AssetId);
		AssetObj->TryGetStringField(TEXT("display_name"), OutAsset.DisplayName);
		AssetObj->TryGetNumberField(TEXT("target_height_m"), OutAsset.TargetHeightM);

		const TArray<TSharedPtr<FJsonValue>>* SlotsArray = nullptr;
		if (AssetObj->TryGetArrayField(TEXT("material_slots"), SlotsArray))
		{
			ParseMaterialSlots(SlotsArray, OutAsset.MaterialSlots);
		}

		const TArray<TSharedPtr<FJsonValue>>* VariantsArray = nullptr;
		if (AssetObj->TryGetArrayField(TEXT("variants"), VariantsArray))
		{
			ParseVariants(VariantsArray, OutAsset.Variants);
		}

		const TSharedPtr<FJsonObject>* UnityObj = nullptr;
		if (AssetObj->TryGetObjectField(TEXT("unity"), UnityObj))
		{
			ParseUnityHints(*UnityObj, OutAsset.Unity);
		}

		return !OutAsset.AssetId.IsEmpty();
	}
}

bool FImmersiveStudioManifestParser::ParseFromFile(
	const FString& ManifestPath,
	FImmersiveStudioJobManifest& OutManifest,
	FString& OutError)
{
	FString JsonText;
	if (!FFileHelper::LoadFileToString(JsonText, *ManifestPath))
	{
		OutError = FString::Printf(TEXT("Could not read manifest: %s"), *ManifestPath);
		return false;
	}

	if (!JsonText.IsEmpty() && JsonText[0] == 0xFEFF)
	{
		JsonText.RemoveAt(0);
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		OutError = TEXT("manifest.json could not be parsed.");
		return false;
	}

	Root->TryGetStringField(TEXT("job_id"), OutManifest.JobId);

	const TArray<TSharedPtr<FJsonValue>>* AssetsArray = nullptr;
	if (!Root->TryGetArrayField(TEXT("assets"), AssetsArray) || !AssetsArray || AssetsArray->Num() == 0)
	{
		OutError = TEXT("manifest.json has no assets.");
		return false;
	}

	for (const TSharedPtr<FJsonValue>& Value : *AssetsArray)
	{
		const TSharedPtr<FJsonObject>* AssetObj = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(AssetObj) || !AssetObj->IsValid())
		{
			continue;
		}

		FImmersiveStudioAssetSpec Asset;
		if (ParseAsset(*AssetObj, Asset))
		{
			OutManifest.Assets.Add(MoveTemp(Asset));
		}
	}

	if (OutManifest.Assets.Num() == 0)
	{
		OutError = TEXT("manifest.json assets could not be parsed.");
		return false;
	}

	if (OutManifest.JobId.IsEmpty())
	{
		OutManifest.JobId = TEXT("unknown_job");
	}

	return true;
}
