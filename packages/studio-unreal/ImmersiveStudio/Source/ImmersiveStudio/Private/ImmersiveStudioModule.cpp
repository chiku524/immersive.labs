#include "ImmersiveStudioModule.h"

#include "ImmersiveStudioImporter.h"

#include "Framework/Application/SlateApplication.h"
#include "LevelEditor.h"
#include "ToolMenus.h"

#define LOCTEXT_NAMESPACE "ImmersiveStudioModule"

void FImmersiveStudioModule::StartupModule()
{
	UToolMenus::RegisterStartupCallback(
		FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FImmersiveStudioModule::RegisterMenus));
}

void FImmersiveStudioModule::ShutdownModule()
{
	UToolMenus::UnRegisterStartupCallback(this);
	UToolMenus::UnregisterOwner(this);
}

void FImmersiveStudioModule::RegisterMenus()
{
	FToolMenuOwnerScoped OwnerScoped(this);

	UToolMenu* Menu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools");
	if (!Menu)
	{
		return;
	}

	FToolMenuSection& Section = Menu->FindOrAddSection("ImmersiveLabsStudio");
	Section.AddMenuEntry(
		"ImportStudioPack",
		LOCTEXT("ImportStudioPackLabel", "Import Studio Pack..."),
		LOCTEXT(
			"ImportStudioPackTooltip",
			"Import a Video Game Generation Studio pack folder (manifest.json, Models, Textures)."),
		FSlateIcon(),
		FUIAction(FExecuteAction::CreateRaw(this, &FImmersiveStudioModule::ImportStudioPack)));
}

void FImmersiveStudioModule::ImportStudioPack()
{
	FImmersiveStudioImporter::ImportPackInteractive();
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FImmersiveStudioModule, ImmersiveStudio)
