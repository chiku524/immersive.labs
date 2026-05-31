#include "ImmersiveStudioImporter.h"

#include "ImmersiveStudioManifest.h"
#include "ImmersiveStudioMaterialFactory.h"

#include "AssetImportTask.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetToolsModule.h"
#include "DesktopPlatformModule.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "Framework/Notifications/NotificationManager.h"
#include "HAL/FileManager.h"
#include "Internationalization/Regex.h"
#include "Misc/MessageDialog.h"
#include "Misc/ScopedSlowTask.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"
#include "Widgets/Notifications/SNotificationList.h"

namespace
{
	struct FPbrTextureSet
	{
		FString AlbedoSourcePath;
		FString NormalSourcePath;
		FString OrmSourcePath;
		UTexture2D* Albedo = nullptr;
		UTexture2D* Normal = nullptr;
		UTexture2D* Orm = nullptr;
	};

	const FRegexPattern PbrNamePattern(TEXT("^(.*)_(albedo|normal|orm)$"), ERegexPatternFlags::CaseInsensitive);

	FString SanitizeAssetName(FString Value)
	{
		Value.TrimStartAndEndInline();
		if (Value.IsEmpty())
		{
			return TEXT("job");
		}

		FString Safe;
		Safe.Reserve(Value.Len());
		for (const TCHAR Ch : Value)
		{
			if (FChar::IsAlnum(Ch) || Ch == TEXT('_') || Ch == TEXT('-'))
			{
				Safe.AppendChar(Ch);
			}
			else
			{
				Safe.AppendChar(TEXT('_'));
			}
		}

		return Safe;
	}

	bool IsPbrRole(const FString& Role)
	{
		const FString Lower = Role.ToLower();
		return Lower == TEXT("albedo") || Lower == TEXT("normal") || Lower == TEXT("orm");
	}

	FString GetPreferredPbrMaterialBase(const FImmersiveStudioAssetSpec& Asset)
	{
		if (Asset.Variants.Num() == 0 || Asset.MaterialSlots.Num() == 0)
		{
			return FString();
		}

		const FString VariantId = Asset.Variants[0].VariantId;
		for (const FImmersiveStudioMaterialSlot& Slot : Asset.MaterialSlots)
		{
			if (Slot.Id.IsEmpty())
			{
				continue;
			}

			if (IsPbrRole(Slot.Role))
			{
				return FString::Printf(TEXT("%s_%s"), *VariantId, *Slot.Id);
			}
		}

		return FString::Printf(TEXT("%s_%s"), *VariantId, *Asset.MaterialSlots[0].Id);
	}

	TArray<FString> GetOrderedPbrMaterialBases(const FImmersiveStudioAssetSpec& Asset)
	{
		TArray<FString> Ordered;
		TSet<FString> Seen;

		TArray<FImmersiveStudioMaterialSlot> TextureSlots;
		for (const FImmersiveStudioMaterialSlot& Slot : Asset.MaterialSlots)
		{
			if (Slot.Id.IsEmpty() || !IsPbrRole(Slot.Role))
			{
				continue;
			}
			TextureSlots.Add(Slot);
		}

		for (const FImmersiveStudioVariant& Variant : Asset.Variants)
		{
			if (Variant.VariantId.IsEmpty())
			{
				continue;
			}

			for (const FImmersiveStudioMaterialSlot& Slot : TextureSlots)
			{
				const FString Key = FString::Printf(TEXT("%s_%s"), *Variant.VariantId, *Slot.Id);
				if (Seen.Add(Key))
				{
					Ordered.Add(Key);
				}
			}
		}

		return Ordered;
	}

	bool ImportedMaterialMatchesPbrBase(const FString& ImportedName, const FString& PbrBase)
	{
		if (ImportedName.IsEmpty() || PbrBase.IsEmpty())
		{
			return false;
		}

		FString Name = ImportedName;
		Name.ReplaceInline(TEXT(" (Instance)"), TEXT(""));
		Name.TrimStartAndEndInline();

		if (Name.Equals(PbrBase, ESearchCase::IgnoreCase))
		{
			return true;
		}

		const FString Prefix = PbrBase + TEXT(".");
		return Name.StartsWith(Prefix, ESearchCase::IgnoreCase);
	}

	void ConfigureImportedTexture(UTexture2D* Texture, bool bNormalMap, bool bSRGB)
	{
		if (!Texture)
		{
			return;
		}

		Texture->SRGB = bSRGB;
		Texture->CompressionSettings = bNormalMap ? TC_Normalmap : TC_Default;
		Texture->UpdateResource();
		Texture->MarkPackageDirty();
	}

	UTexture2D* ImportTextureFile(
		IAssetTools& AssetTools,
		const FString& SourcePath,
		const FString& DestinationContentPath,
		bool bNormalMap,
		bool bSRGB)
	{
		UAssetImportTask* Task = NewObject<UAssetImportTask>();
		Task->Filename = SourcePath;
		Task->DestinationPath = DestinationContentPath;
		Task->bAutomated = true;
		Task->bSave = true;
		Task->bReplaceExisting = true;

		AssetTools.ImportAssetTasks({Task});

		for (const FString& ImportedPath : Task->ImportedObjectPaths)
		{
			if (UTexture2D* Texture = LoadObject<UTexture2D>(nullptr, *ImportedPath))
			{
				ConfigureImportedTexture(Texture, bNormalMap, bSRGB);
				return Texture;
			}
		}

		return nullptr;
	}

	UStaticMesh* ImportMeshFile(IAssetTools& AssetTools, const FString& SourcePath, const FString& DestinationContentPath)
	{
		UAssetImportTask* Task = NewObject<UAssetImportTask>();
		Task->Filename = SourcePath;
		Task->DestinationPath = DestinationContentPath;
		Task->bAutomated = true;
		Task->bSave = true;
		Task->bReplaceExisting = true;

		AssetTools.ImportAssetTasks({Task});

		for (const FString& ImportedPath : Task->ImportedObjectPaths)
		{
			if (UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *ImportedPath))
			{
				return Mesh;
			}
		}

		return nullptr;
	}

	void ApplyBoxCollisionIfConfigured(UStaticMesh* StaticMesh, const FImmersiveStudioAssetSpec& Asset)
	{
		if (!StaticMesh || !Asset.Unity.Collider.Equals(TEXT("box"), ESearchCase::IgnoreCase))
		{
			return;
		}

		UBodySetup* BodySetup = StaticMesh->GetBodySetup();
		if (!BodySetup)
		{
			StaticMesh->CreateBodySetup();
			BodySetup = StaticMesh->GetBodySetup();
		}

		if (!BodySetup)
		{
			return;
		}

		const FBox Bounds = StaticMesh->GetBoundingBox();
		BodySetup->AggGeom.BoxElems.Reset();

		FKBoxElem BoxElem;
		BoxElem.Center = Bounds.GetCenter();
		BoxElem.X = FMath::Max(Bounds.GetExtent().X * 2.f, KINDA_SMALL_NUMBER);
		BoxElem.Y = FMath::Max(Bounds.GetExtent().Y * 2.f, KINDA_SMALL_NUMBER);
		BoxElem.Z = FMath::Max(Bounds.GetExtent().Z * 2.f, KINDA_SMALL_NUMBER);
		BodySetup->AggGeom.BoxElems.Add(BoxElem);
		BodySetup->CollisionTraceFlag = CTF_UseSimpleAsComplex;
		StaticMesh->Build();
		StaticMesh->MarkPackageDirty();
	}

	UMaterialInterface* PickSlotMaterial(
		int32 SlotIndex,
		const FString& ImportedMaterialName,
		UMaterialInterface* FallbackMaterial,
		const TMap<FString, UMaterialInstanceConstant*>& MaterialsByBase,
		const TArray<UMaterialInstanceConstant*>& OrderedMaterials)
	{
		if (!ImportedMaterialName.IsEmpty())
		{
			for (const TPair<FString, UMaterialInstanceConstant*>& Pair : MaterialsByBase)
			{
				if (ImportedMaterialMatchesPbrBase(ImportedMaterialName, Pair.Key))
				{
					return Pair.Value;
				}
			}
		}

		if (OrderedMaterials.IsValidIndex(SlotIndex))
		{
			return OrderedMaterials[SlotIndex];
		}

		if (OrderedMaterials.Num() > 0)
		{
			return OrderedMaterials[SlotIndex % OrderedMaterials.Num()];
		}

		return FallbackMaterial;
	}

	void AssignMaterialsToStaticMesh(
		UStaticMesh* StaticMesh,
		UMaterialInterface* FallbackMaterial,
		const TMap<FString, UMaterialInstanceConstant*>& MaterialsByBase,
		const TArray<FString>& OrderedBases)
	{
		if (!StaticMesh)
		{
			return;
		}

		TArray<UMaterialInstanceConstant*> OrderedMaterials;
		for (const FString& Base : OrderedBases)
		{
			if (UMaterialInstanceConstant* const* Found = MaterialsByBase.Find(Base))
			{
				OrderedMaterials.Add(*Found);
			}
		}

		TArray<FStaticMaterial>& StaticMaterials = StaticMesh->GetStaticMaterials();
		if (StaticMaterials.Num() == 0)
		{
			FStaticMaterial Slot;
			Slot.MaterialInterface = PickSlotMaterial(0, FString(), FallbackMaterial, MaterialsByBase, OrderedMaterials);
			StaticMaterials.Add(Slot);
		}
		else
		{
			for (int32 Index = 0; Index < StaticMaterials.Num(); ++Index)
			{
				FString ImportedName;
				if (StaticMaterials[Index].MaterialInterface)
				{
					ImportedName = StaticMaterials[Index].MaterialInterface->GetName();
				}

				StaticMaterials[Index].MaterialInterface = PickSlotMaterial(
					Index,
					ImportedName,
					FallbackMaterial,
					MaterialsByBase,
					OrderedMaterials);
			}
		}

		StaticMesh->SetStaticMaterials(StaticMaterials);
		StaticMesh->MarkPackageDirty();
	}

	TMap<FString, FPbrTextureSet> BuildPbrGroupsFromDisk(const FString& TexturesDir)
	{
		TMap<FString, FPbrTextureSet> Groups;
		TArray<FString> Files;
		IFileManager::Get().FindFiles(Files, *(TexturesDir / TEXT("*.png")), true, false);

		for (const FString& FileName : Files)
		{
			if (FileName.StartsWith(TEXT("README"), ESearchCase::IgnoreCase))
			{
				continue;
			}

			const FString BaseName = FPaths::GetBaseFilename(FileName);
			FRegexMatcher Matcher(PbrNamePattern, BaseName);
			if (!Matcher.FindNext())
			{
				continue;
			}

			const FString GroupKey = Matcher.GetCaptureGroup(1);
			const FString Role = Matcher.GetCaptureGroup(2).ToLower();
			FPbrTextureSet& Set = Groups.FindOrAdd(GroupKey);
			const FString FullPath = TexturesDir / FileName;

			if (Role == TEXT("albedo"))
			{
				Set.AlbedoSourcePath = FullPath;
			}
			else if (Role == TEXT("normal"))
			{
				Set.NormalSourcePath = FullPath;
			}
			else if (Role == TEXT("orm"))
			{
				Set.OrmSourcePath = FullPath;
			}
		}

		return Groups;
	}
}

void FImmersiveStudioImporter::ImportPackInteractive()
{
	IDesktopPlatform* DesktopPlatform = FDesktopPlatformModule::Get().GetDesktopPlatform();
	if (!DesktopPlatform)
	{
		return;
	}

	const void* ParentWindow = FSlateApplication::Get().FindBestParentWindowHandleForDialogs(nullptr);
	FString PackRoot;
	const bool bSelected = DesktopPlatform->OpenDirectoryDialog(
		ParentWindow,
		TEXT("Select studio pack folder (contains manifest.json)"),
		FPaths::ProjectDir(),
		PackRoot);

	if (!bSelected || PackRoot.IsEmpty())
	{
		return;
	}

	const FString ManifestPath = FPaths::Combine(PackRoot, TEXT("manifest.json"));
	if (!FPaths::FileExists(ManifestPath))
	{
		FMessageDialog::Open(
			EAppMsgType::Ok,
			NSLOCTEXT("ImmersiveStudio", "MissingManifest", "Could not find manifest.json in the selected folder."));
		return;
	}

	FImmersiveStudioJobManifest Manifest;
	FString ParseError;
	if (!FImmersiveStudioManifestParser::ParseFromFile(ManifestPath, Manifest, ParseError))
	{
		FMessageDialog::Open(EAppMsgType::Ok, FText::FromString(ParseError));
		return;
	}

	const FString JobId = SanitizeAssetName(Manifest.JobId);
	const FString ImportRoot = FString::Printf(TEXT("/Game/ImmersiveStudioImports/%s"), *JobId);

	FScopedSlowTask SlowTask(static_cast<float>(Manifest.Assets.Num() * 4), NSLOCTEXT("ImmersiveStudio", "Importing", "Importing studio pack..."));
	SlowTask.MakeDialog(true);

	IAssetTools& AssetTools = FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools").Get();
	int32 ImportedMeshCount = 0;
	int32 ImportedMaterialCount = 0;

	for (const FImmersiveStudioAssetSpec& Asset : Manifest.Assets)
	{
		SlowTask.EnterProgressFrame(1.f, FText::FromString(FString::Printf(TEXT("Importing %s"), *Asset.AssetId)));

		const FString AssetContentPath = ImportRoot / SanitizeAssetName(Asset.AssetId);
		const FString MaterialsContentPath = AssetContentPath / TEXT("Materials");
		const FString TexturesDir = FPaths::Combine(PackRoot, TEXT("Textures"), Asset.AssetId);
		const FString ModelsDir = FPaths::Combine(PackRoot, TEXT("Models"), Asset.AssetId);

		TMap<FString, FPbrTextureSet> PbrGroups;
		if (FPaths::DirectoryExists(TexturesDir))
		{
			PbrGroups = BuildPbrGroupsFromDisk(TexturesDir);
		}

		TMap<FString, UMaterialInstanceConstant*> MaterialsByBase;
		UMaterialInstanceConstant* PreferredMaterial = nullptr;

		for (TPair<FString, FPbrTextureSet>& Pair : PbrGroups)
		{
			FPbrTextureSet& Set = Pair.Value;
			if (Set.AlbedoSourcePath.IsEmpty())
			{
				continue;
			}

			Set.Albedo = ImportTextureFile(AssetTools, Set.AlbedoSourcePath, AssetContentPath, false, true);
			if (Set.NormalSourcePath.IsEmpty() == false)
			{
				Set.Normal = ImportTextureFile(AssetTools, Set.NormalSourcePath, AssetContentPath, true, false);
			}
			if (Set.OrmSourcePath.IsEmpty() == false)
			{
				Set.Orm = ImportTextureFile(AssetTools, Set.OrmSourcePath, AssetContentPath, false, false);
			}

			const FString MaterialName = Pair.Key + TEXT("_Inst");
			if (UMaterialInstanceConstant* MaterialInstance = FImmersiveStudioMaterialFactory::CreateInstanceForPbrGroup(
					MaterialsContentPath,
					MaterialName,
					Set.Albedo,
					Set.Normal,
					Set.Orm))
			{
				MaterialsByBase.Add(Pair.Key, MaterialInstance);
				++ImportedMaterialCount;
			}
		}

		const FString PreferredBase = GetPreferredPbrMaterialBase(Asset);
		if (!PreferredBase.IsEmpty())
		{
			if (UMaterialInstanceConstant* const* Found = MaterialsByBase.Find(PreferredBase))
			{
				PreferredMaterial = *Found;
			}
		}

		if (!PreferredMaterial && MaterialsByBase.Num() > 0)
		{
			for (TPair<FString, UMaterialInstanceConstant*>& Pair : MaterialsByBase)
			{
				PreferredMaterial = Pair.Value;
				break;
			}
		}

		TArray<FString> OrderedBases = GetOrderedPbrMaterialBases(Asset);

		if (FPaths::DirectoryExists(ModelsDir))
		{
			TArray<FString> MeshFiles;
			TArray<FString> GlbFiles;
			TArray<FString> GltfFiles;
			IFileManager::Get().FindFiles(GlbFiles, *(ModelsDir / TEXT("*.glb")), true, false);
			IFileManager::Get().FindFiles(GltfFiles, *(ModelsDir / TEXT("*.gltf")), true, false);
			MeshFiles.Append(GlbFiles);
			MeshFiles.Append(GltfFiles);

			for (const FString& MeshFile : MeshFiles)
			{
				if (MeshFile.StartsWith(TEXT("README"), ESearchCase::IgnoreCase))
				{
					continue;
				}

				const FString MeshPath = ModelsDir / MeshFile;
				if (UStaticMesh* StaticMesh = ImportMeshFile(AssetTools, MeshPath, AssetContentPath))
				{
					AssignMaterialsToStaticMesh(StaticMesh, PreferredMaterial, MaterialsByBase, OrderedBases);
					ApplyBoxCollisionIfConfigured(StaticMesh, Asset);
					++ImportedMeshCount;
				}
			}
		}
	}

	FAssetRegistryModule& AssetRegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>("AssetRegistry");
	AssetRegistryModule.Get().ScanPathsSynchronous({ImportRoot}, true);

	FNotificationInfo Info(FText::Format(
		NSLOCTEXT("ImmersiveStudio", "ImportDone", "Studio import finished for job `{0}`. Assets live under {1}."),
		FText::FromString(JobId),
		FText::FromString(ImportRoot)));
	Info.ExpireDuration = 8.f;
	FSlateNotificationManager::Get().AddNotification(Info);

	if (ImportedMeshCount == 0 && ImportedMaterialCount == 0)
	{
		FMessageDialog::Open(
			EAppMsgType::Ok,
			NSLOCTEXT(
				"ImmersiveStudio",
				"ImportPartial",
				"Import finished but no meshes or materials were found. Check Models/ and Textures/ in the pack."));
	}
}
