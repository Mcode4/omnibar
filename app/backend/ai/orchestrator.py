
class AIOrchestrator:

    def handle_message(self, message):
        intent = self.plan(message)

        if intent["use_rag"]:
            context = self.rag_retrieve(message)
            return self.generate_with_context(message, context)
        
        return self.generate(message)
    
    def rag_retrieve(self, message):
        return
    
    def generate_with_context(self, message, context):
        return
    
    def generate(self, message):
        return