import sys

with open("main_simulation.py", "r", encoding="utf-8") as f:
    content = f.read()

# Make run_master_loop async
content = content.replace("def run_master_loop(self, ticks=10):", "async def run_master_loop(self, ticks=10):")

# Change determine_next_action to await
content = content.replace("action_data = determine_next_action(", "action_data = await determine_next_action(")

# Change ground_physical_action to await
content = content.replace("physical_data = ground_physical_action(", "physical_data = await ground_physical_action(")

# Change store_observation to await
content = content.replace("store_observation(state, f\"我看到", "await store_observation(state, f\"我看到")

# Find the loop start and end
loop_start_str = "            for agent_name in agent_names:\n                state = self.agents[agent_name]"
loop_idx = content.find(loop_start_str)

end_str = "            self.clock += timedelta(minutes=15)"
end_idx = content.find(end_str)

loop_body = content[loop_idx:end_idx]

# Replace continue with return in the loop body
loop_body = loop_body.replace("                    continue\n", "                    return\n")

new_loop_body = """            import asyncio
            async def run_agent(agent_name):
                state = self.agents[agent_name]"""

rest_of_loop = loop_body[len(loop_start_str):]
new_loop_body += rest_of_loop

new_loop_body += """
            tasks = [run_agent(aname) for aname in agent_names]
            await asyncio.gather(*tasks)
"""

content = content[:loop_idx] + new_loop_body + content[end_idx:]

# In __main__, run asyncio.run
content = content.replace("sim.run_master_loop(ticks=30)", "import asyncio\n    asyncio.run(sim.run_master_loop(ticks=30))")

with open("main_simulation.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored to async successfully!")
