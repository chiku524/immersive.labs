using UnrealBuildTool;

public class ImmersiveStudio : ModuleRules
{
	public ImmersiveStudio(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(
			new string[]
			{
				"Core",
				"CoreUObject",
				"Engine",
			});

		PrivateDependencyModuleNames.AddRange(
			new string[]
			{
				"AssetRegistry",
				"AssetTools",
				"ContentBrowser",
				"DesktopPlatform",
				"EditorFramework",
				"EditorStyle",
				"ImageWrapper",
				"InputCore",
				"Json",
				"JsonUtilities",
				"MaterialEditor",
				"PhysicsCore",
				"Projects",
				"Slate",
				"SlateCore",
				"ToolMenus",
				"UnrealEd",
			});
	}
}
