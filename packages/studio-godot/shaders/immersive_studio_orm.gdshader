shader_type spatial;
render_mode cull_back;

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D orm_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float metallic_scale = 0.25;
uniform float roughness_scale = 0.85;
uniform float ao_strength = 1.0;
uniform vec3 emission_tint : source_color = vec3(1.0);
uniform float emission_energy = 0.0;

void fragment() {
	vec4 albedo_sample = texture(albedo_tex, UV);
	vec3 orm = texture(orm_tex, UV).rgb;

	ALBEDO = albedo_sample.rgb;
	ALPHA = albedo_sample.a;
	AO = mix(1.0, orm.r, ao_strength);
	ROUGHNESS = clamp(orm.g * roughness_scale, 0.04, 1.0);
	METALLIC = clamp(orm.b * metallic_scale, 0.0, 1.0);
	EMISSION = emission_tint * emission_energy;
}
