function render(){if(!DATA)return;renderCards();isOrg()?renderOrg():(isResumo()?renderResumo():(isDistribSheet()?renderDistribCompact():(isSheet()?renderSheet():renderMatrix())))}
